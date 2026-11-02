"""Serial, observational harness. No changes to workflow decisions or requests."""
import copy
import json
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from uuid import uuid4
from unittest.mock import patch

from csa_workflow import agents, services
from csa_workflow.state import WorkflowState
from csa_workflow.faults import FaultInjector
from csa_workflow.llm import OpenAIClient
from run_fault_audit import audit

PROFILE = 'qa_first_missing_once_v1'


class ProviderClient(OpenAIClient):
    """Same request as OpenAIClient; retains the complete provider usage object."""
    def complete(self, system, user):
        self.last_metadata = None
        response = self._client.chat.completions.create(
            model=self.model, temperature=self.temperature,
            messages=[{'role': 'system', 'content': system},
                      {'role': 'user', 'content': user}])
        usage = getattr(response, 'usage', None)
        self.last_metadata = {
            'usage': usage.model_dump() if usage is not None else None,
            'response_id': getattr(response, 'id', None),
            'returned_model': getattr(response, 'model', None),
            'finish_reason': response.choices[0].finish_reason,
        }
        return response.choices[0].message.content or ''


class Observer:
    def __init__(self, case, client, folder, condition, run_id=None):
        self.case, self.client, self.condition = case, client, condition
        self.run_id = run_id or str(uuid4())
        self.events, self.calls, self.drafts = [], [], []
        self.context = {'stage': 'initialization', 'iteration': 0, 'issue': None}
        self.parent = None
        self.last_qa = None
        self.last_router = None
        self.last_helper = None
        self.started = time.perf_counter()
        self.file = (folder / 'trace.jsonl').open('x')

    def emit(self, event, depends_on=None, **fields):
        row = dict(run_id=self.run_id, event_id=f'{self.run_id}:e{len(self.events)+1}',
                   event=event, previous_event_id=self.events[-1]['event_id'] if self.events else None, elapsed_seconds=time.perf_counter()-self.started,
                   depends_on=[d for d in (depends_on if depends_on is not None else [self.parent]) if d],
                   **self.context, **fields)
        self.events.append(copy.deepcopy(row))
        self.file.write(json.dumps(row, ensure_ascii=False)+'\n')
        self.file.flush()
        return row['event_id']

    @contextmanager
    def scope(self, stage, state, issue=None, parent=None):
        previous = self.context, self.parent
        self.context = dict(stage=stage, iteration=state.iteration, issue=issue)
        self.parent = parent
        try:
            yield
        finally:
            self.context, self.parent = previous

    def complete(self, system, user):
        # Invoked synchronously at the actual LLM seam, inside the current stage.
        call_id = f'{self.run_id}:model{len(self.calls)+1}'
        request = self.emit('model_request', call_id=call_id, system_prompt=system,
                            user_prompt=user, requested_model=getattr(self.client,'model',None),
                            temperature=getattr(self.client,'temperature',None))
        entry = dict(call_id=call_id, request_event_id=request, **self.context)
        self.calls.append(entry)
        start = time.perf_counter()
        try:
            answer = self.client.complete(system, user)
            metadata = copy.deepcopy(getattr(self.client, 'last_metadata', None)) or {'usage': None}
            entry.update(status='ok', **metadata)
            entry['response_text'] = answer
            return answer
        except Exception as exc:
            entry.update(status='error', usage=None, error_type=type(exc).__name__,
                         status_code=getattr(exc,'status_code',None))
            raise
        finally:
            entry['duration_seconds'] = time.perf_counter()-start
            self.parent = self.emit('model_result', depends_on=[request], **{k:v for k,v in entry.items() if k not in self.context})

    def run(self):
        decompose, decide = agents.RouterAgent.decompose, agents.RouterAgent.decide
        handle, review = agents._HelperAgent.handle, agents.QAAgent.review
        tool, log = services.call_tool, WorkflowState.log
        inject = FaultInjector.on_qa_feedback
        boundaries = []
        snapshots = []
        tool_count = 0

        def decomposed(agent, state):
            with self.scope('classification', state):
                decompose(agent, state)
                self.emit('classification_result', issues=list(state.issues))

        def routed(agent, state, feedback):
            with self.scope('router', state, parent=self.last_qa):
                received = self.emit('router_input', feedback=asdict(feedback) if feedback else None,
                                     state=asdict(state))
                target = decide(agent, state, feedback)
                self.last_router = self.emit('router_selection', depends_on=[received],
                    selected_issue=target, selected_was_resolved=state.is_resolved(target),
                    unresolved_at_input=[i.issue_type for i in state.open_issues()])
                return target

        def handled(agent, issue, state):
            with self.scope('helper_'+agent.route, state, issue, self.last_router):
                action = self.emit('helper_start', state=asdict(state))
                self.parent = action
                event_start = len(self.events)
                before = len(state.issues[issue].evidence)
                agents._HelperAgent.handle(agent, issue, state)
                evidence = [asdict(e) for e in state.issues[issue].evidence[before:]]
                end = self.emit('helper_end', evidence=evidence, state=asdict(state))
                self.last_helper = end
                for e in evidence:
                    if e['source'] != 'support_doc':
                        self.drafts.append(dict(draft_id=end, issue=issue, iteration=state.iteration,
                                                answer=e['content'], evidence=evidence,
                                                original_request=state.user_query,
                                                tool_observations=[copy.deepcopy(x) for x in self.events[event_start:] if x['event']=='tool_result']))

        def called(issue_type, **kwargs):
            nonlocal tool_count
            tool_count += 1
            call_id = f'{self.run_id}:tool{tool_count}'
            request = self.emit('tool_request', call_id=call_id, arguments=dict(issue_type=issue_type, **kwargs))
            start = time.perf_counter()
            try:
                result = tool(issue_type, **kwargs)
                self.parent = self.emit('tool_result', depends_on=[request], call_id=call_id,
                          result=asdict(result), duration_seconds=time.perf_counter()-start)
                return result
            except Exception as exc:
                self.emit('tool_error', depends_on=[request], call_id=call_id,
                          error_type=type(exc).__name__, duration_seconds=time.perf_counter()-start)
                raise

        def injected(injector, iteration, feedback, **kwargs):
            before = asdict(feedback)
            result = inject(injector, iteration, feedback, **kwargs)
            boundary = dict(original_value=before, injected_value=asdict(result),
                            effective_mutation=before != asdict(result),
                            profile_event=copy.deepcopy(getattr(injector, 'last_profile_event', None)))
            boundary['event_id'] = self.emit('qa_injection_boundary', **boundary)
            self.parent = boundary['event_id']
            boundaries.append(boundary)
            return result

        def reviewed(agent, state):
            with self.scope('qa', state, parent=self.last_helper or self.last_router):
                result = review(agent, state)
                snapshots.append(asdict(state))
                self.last_qa = self.emit('qa_feedback', feedback=asdict(result), state=asdict(state))
                return result

        def logged(state, stage, **kwargs):
            log(state, stage, **kwargs)
            # Orchestrator actions occur outside helper/QA method scopes.
            with self.scope(stage, state, kwargs.get('issue'), self.last_router):
                self.emit('workflow_action', action=stage, details=kwargs)

        self.emit('run_start', case=self.case.raw, condition=self.condition)
        try:
            with ExitStack() as stack:
                for obj, name, replacement in ((agents.RouterAgent,'decompose',decomposed),
                    (agents.RouterAgent,'decide',routed), (agents.TechnicalAgent,'handle',handled), (agents.BillingAgent,'handle',handled),
                    (agents.QAAgent,'review',reviewed), (services,'call_tool',called),
                    (WorkflowState,'log',logged), (FaultInjector,'on_qa_feedback',injected)):
                    stack.enter_context(patch.object(obj, name, replacement))
                report = audit(self.case, self if self.client is not None else None,
                               profile=PROFILE if self.condition == 'fault' else None)
            report['audit_run_id'] = report['run_id']
            report['run_status'] = 'completed'
        except Exception as exc:
            report = dict(run_status='error', error_type=type(exc).__name__,
                          status_code=getattr(exc,'status_code',None), result=None)
            self.emit('runtime_error', **report)
        report.update(run_id=self.run_id, case_id=self.case.case_id, condition=self.condition,
                      elapsed_seconds=time.perf_counter()-self.started,
                      model_calls=len(self.calls), tool_calls=tool_count,
                      helper_calls=sum(e['event']=='helper_start' for e in self.events),
                      usage_records=self.calls, drafts=self.drafts, qa_snapshots=snapshots,
                      injection_boundaries=boundaries)
        # Null is unknown, zero is observed zero; expose known subtotals separately.
        report['provider_tokens'] = {}
        for field in ('prompt_tokens','completion_tokens','total_tokens'):
            values = [(c.get('usage') or {}).get(field) for c in self.calls]
            report['provider_tokens'][field] = dict(
                total=sum(values) if all(v is not None for v in values) else None,
                known_subtotal=sum(v for v in values if v is not None),
                missing_calls=sum(v is None for v in values))
        for e in report.get('events', []):
            e['audit_run_id'] = e.get('run_id')
            e['run_id'] = self.run_id
            e['qa_event_id'] = next((x['event_id'] for x in self.events if x['event']=='qa_feedback' and x['iteration']==e['iteration']),None)
            e['router_event_id'] = next((x['event_id'] for x in self.events if x['event']=='router_input' and e['qa_event_id'] in x['depends_on']),None)
            e['event_id'] = self.emit('injection_audit', depends_on=[e['qa_event_id']], injection=e)
        self.emit('run_end', run_status=report['run_status'])
        self.file.close()
        return report


def observe(case, client, folder, condition, run_id=None):
    observer = Observer(case, client, folder, condition, run_id)
    try:
        report = observer.run()
        (folder/'result.json').write_text(json.dumps(report, indent=2))
        return report
    finally:
        observer.file.close()
