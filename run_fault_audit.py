"""Activation evidence, never recovery scoring. Offline by default; no baseline edits."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, is_dataclass, replace
import json
import hashlib
import inspect
import sys
from collections import Counter
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch

from csa_workflow import agents
from csa_workflow.dataset import load_cases
from csa_workflow.faults import FaultInjector, QA_FIRST_MISSING_ONCE_V1
from csa_workflow.orchestrator import run_case


def value(x):
    return deepcopy(asdict(x) if is_dataclass(x) else x)


def audit(case, llm=None, qa_trigger=None, profile=None):
    original_config = deepcopy(case.fault_config)
    if profile is not None:
        if profile != QA_FIRST_MISSING_ONCE_V1 or case.fault_type != 'qa_corruption':
            raise ValueError('QA profile requires a QA-corruption case and a known profile')
        if qa_trigger is not None:
            raise ValueError('Profile cannot be combined with a legacy trigger override')
        case = replace(case, fault_config={'profile': profile, 'target_stage': 'qa_to_router'})
    run_id = str(uuid4())
    if qa_trigger is not None and case.fault_type == 'qa_corruption':
        case = replace(case, fault_config={**case.fault_config, 'trigger_iteration': qa_trigger})
    events = []
    context = {'iteration': 0}
    hooks = {'timeout': ('on_tool_call', 'simulated_tool'),
             'prompt_injection': ('on_retrieved_text', 'retrieved_support_text'),
             'helper_corruption': ('on_helper_output', 'helper_output'),
             'qa_corruption': ('on_qa_feedback', 'qa_to_router')}
    decide = agents.RouterAgent.decide
    handle = agents._HelperAgent.handle
    generate = agents.generate_response

    def consume(event, consumer, received):
        event['downstream_consumer'] = consumer
        event['received_value'] = value(received)
        event['consumed'] = True
        event['effective_consumed'] = event['effective_mutation'] and event['injected_value'] == value(received)
        event['output_disposition'] = 'received_unchanged' if event['injected_value'] == value(received) else 'overwritten'

    def route(self, state, feedback):
        target = decide(self, state, feedback)
        if feedback is not None and case.fault_type == 'qa_corruption':
            consume(events[-1], 'RouterAgent.decide', feedback)
            events[-1]['next_router'] = dict(
                iteration=state.iteration, input=value(feedback), selected_issue=target,
                selected_was_resolved=state.is_resolved(target),
                unresolved_at_input=[i.issue_type for i in state.open_issues()])
        context['iteration'] = state.iteration
        return target

    source, first_line = inspect.getsourcelines(handle)
    branch_line = first_line + next(i for i, line in enumerate(source)
                                   if 'if result.status == "timeout":' in line)

    def helper(self, issue, state):
        # Read the actual local ToolResult immediately before its status branch.
        # This observer changes no workflow values and restores existing tracing.
        previous_trace = sys.gettrace()
        def trace(frame, event, arg):
            if (frame.f_code is handle.__code__ and event == 'line'
                    and frame.f_lineno == branch_line
                    and case.fault_type in ('timeout', 'helper_corruption')):
                consume(events[-1], '_HelperAgent.handle.status/record', frame.f_locals['result'])
            return trace
        try:
            sys.settrace(trace)
            return handle(self, issue, state)
        finally:
            sys.settrace(previous_trace)

    def draft(client, issue, doc, record, **kwargs):
        if case.fault_type == 'prompt_injection':
            consume(events[-1], 'generate_response.support_document_untrusted', doc)
        return generate(client, issue, doc, record, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(agents.RouterAgent, 'decide', route))
        stack.enter_context(patch.object(agents._HelperAgent, 'handle', helper))
        stack.enter_context(patch.object(agents, 'generate_response', draft))
        if case.fault_type in hooks:
            name, stage = hooks[case.fault_type]
            original = getattr(FaultInjector, name)
            def hook(self, target, incoming, **kwargs):
                before = value(incoming)
                outgoing = original(self, target, incoming, **kwargs)
                after = value(outgoing)
                effective = before != after
                reason = None
                if not effective:
                    cfg = self.cfg
                    if case.fault_type == 'qa_corruption':
                        if cfg.get('target_stage') != stage: reason = 'target_stage_mismatch'
                        elif target < cfg.get('trigger_iteration', 2): reason = 'before_trigger_iteration'
                        elif incoming.missing_issue != cfg.get('mutation', {}).get('original'): reason = 'original_label_mismatch_or_no_missing_issue'
                        else: reason = 'no_op_mutation'
                    elif case.fault_type == 'helper_corruption':
                        reason = 'target_agent_mismatch' if target != cfg.get('target_agent') else 'already_injected_or_no_op'
                    else: reason = 'target_stage_mismatch_or_no_op'
                events.append(dict(case_id=case.case_id, fault_type=case.fault_type,
                    target_stage=stage, configured_target_stage=self.cfg.get('target_stage'),
                    iteration=target if stage == 'qa_to_router' else context['iteration'],
                    configured_trigger_iteration=self.cfg.get('trigger_iteration'), target=target,
                    injection_point_reached=True, original_value=before, injected_value=after,
                    effective_mutation=effective, skip_reason=reason, consumed=False,
                    effective_consumed=False, downstream_consumer=None, received_value=None,
                    output_disposition='not_consumed'))
                if profile is not None:
                    events[-1].update(deepcopy(self.last_profile_event))
                    events[-1]['run_id'] = run_id
                return outgoing
            stack.enter_context(patch.object(FaultInjector, name, hook))
        result = run_case(case, llm)
    for e in events:
        if 'next_router' in e:
            router = e['next_router']
            router['actions'] = [h for h in result.history
                                 if h['iteration'] == router['iteration']
                                 and h['stage'] in ('route', 'no_helper', 'helper_result',
                                                   'helper_timeout', 'helper_unavailable')]
            e['behavioral_effect'] = bool(e['effective_consumed']
                and router['selected_issue'] == e['injected_value']['missing_issue']
                and router['selected_was_resolved']
                and any(h['stage'] == 'route' for h in router['actions']))
        if not e['consumed']:
            e['consumer_skip_reason'] = ('offline_rule_backend_stores_document_but_does_not_use_it_for_answer'
                if case.fault_type == 'prompt_injection' else 'workflow_terminated_before_next_router')
    if not events and case.fault_type != 'none':
        events.append(dict(case_id=case.case_id, fault_type=case.fault_type,
            target_stage=hooks[case.fault_type][1], iteration=None, injection_point_reached=False,
            original_value=None, injected_value=None, effective_mutation=False, consumed=False,
            effective_consumed=False, downstream_consumer=None, received_value=None,
            skip_reason='stage_unreachable_before_termination'))
    return dict(case_id=case.case_id, run_id=run_id, profile=profile or 'original',
        fault_type=case.fault_type,
        original_config=original_config, effective_config=case.fault_config,
        events=events, result=asdict(result), recovery_success=None,
        eligible=any(e.get('eligible', e['effective_mutation']) for e in events),
        actual_mutation_count=sum(e['effective_mutation'] for e in events),
        skip_reasons=sorted({e['skip_reason'] for e in events if e.get('skip_reason')})
            if not any(e['effective_mutation'] for e in events) else [],
        behavioral_effect=any(e.get('behavioral_effect', False) for e in events),
        effective_mutation=any(e['effective_mutation'] for e in events),
        effective_consumed=any(e['effective_consumed'] for e in events))


class ScriptedLLM:
    """Gold classification is test scaffolding, not evidence of LLM accuracy."""
    def __init__(self, issues): self.issues = issues
    def complete(self, system, user):
        if 'classifier' in system: return json.dumps(self.issues)
        if 'QA routing reviewer' in system:
            return json.dumps({'missing_issue': json.loads(user)['unresolved_issues'][0], 'reason': 'mock'})
        return 'Mock helper answer; no semantic accuracy claim.'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--path', default='support_cases_unique40.jsonl')
    p.add_argument('--backend', choices=['rule', 'scripted', 'scripted-reversed', 'openai'], default='rule')
    p.add_argument('--qa-trigger', type=int)
    p.add_argument('--profile', choices=[QA_FIRST_MISSING_ONCE_V1])
    p.add_argument('--fault', choices=['qa_corruption'])
    p.add_argument('--case', action='append')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.profile and args.qa_trigger is not None:
        p.error('--profile and --qa-trigger are mutually exclusive')
    cases = [c for c in load_cases(args.path)
             if (not args.case or c.case_id in args.case)
             and (not (args.fault or args.profile) or c.fault_type == 'qa_corruption')]
    if not cases: p.error('No matching cases')
    client = None
    if args.backend == 'openai':
        from csa_workflow.llm import OpenAIClient
        client = OpenAIClient()
    reports = [audit(c, ScriptedLLM(list(reversed(c.expected_issues)) if args.backend == 'scripted-reversed' else c.expected_issues) if args.backend.startswith('scripted') else client,
                     args.qa_trigger, args.profile) for c in cases]
    summary = {}
    for ft in sorted({c.fault_type for c in cases}):
        group = [r for r in reports if r['fault_type'] == ft]
        summary[ft] = dict(cases=len(group), reached=sum(any(e['injection_point_reached'] for e in r['events']) for r in group),
            eligible=sum(r['eligible'] for r in group),
            mutated=sum(r['effective_mutation'] for r in group), consumed_mutation=sum(r['effective_consumed'] for r in group),
            behavioral_effect=sum(r['behavioral_effect'] for r in group),
            skipped=sum(not r['effective_mutation'] for r in group),
            skipped_case_reasons=dict(Counter(reason for r in group for reason in r['skip_reasons'])))
    output = dict(source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), *Path('csa_workflow').glob('*.py'), Path(args.path)]}, backend=args.backend, qa_trigger_override=args.qa_trigger, summary=summary, cases=reports)
    with open(args.output, 'x') as f: json.dump(output, f, indent=2)
    print(json.dumps(summary, indent=2))

if __name__ == '__main__': main()
