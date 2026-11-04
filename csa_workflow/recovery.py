"""Opt-in recovery experiment; legacy orchestrator and frozen studies stay intact.

Checks use runtime ledger and fresh simulated records, never expected/gold labels.
All modes use the same one-effective-mutation-per-run fault model (recovery-v1).
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from time import perf_counter
from uuid import uuid4

from . import services
from .agents import QAAgent, RouterAgent
from .faults import FaultInjector, QAFeedback
from .llm import generate_response
from .provider_accounting import complete_observed, provider_usage_observer
from .cost_metrics import summarize, METRICS_SCHEMA_VERSION, source_provenance
from .state import Evidence, IssueStatus, WorkflowState
from .taxonomy import ISSUE_ROUTE


class BudgetExceeded(RuntimeError):
    pass


class StageFailure(RuntimeError):
    pass


@dataclass
class RunBudget:
    max_model_calls: int = 40
    max_tool_calls: int = 40
    max_verifications: int = 40
    model_calls: int = 0
    tool_calls: int = 0
    verification_calls: int = 0

    def __post_init__(self):
        if any(v < 0 for v in asdict(self).values()):
            raise ValueError('Budget limits and counters must be nonnegative')

    def take(self, kind):
        field_name = kind + '_calls'
        limit = {'model': self.max_model_calls, 'tool': self.max_tool_calls,
                 'verification': self.max_verifications}[kind]
        if getattr(self, field_name) >= limit:
            raise BudgetExceeded(kind + ' budget exhausted')
        setattr(self, field_name, getattr(self, field_name) + 1)


class _TransientFault:
    def __init__(self, case, emit):
        self.inner = FaultInjector(case.fault_type, case.fault_config)
        self.cfg = self.inner.cfg
        self.used = False
        self.emit = emit

    def apply(self, hook, *args, **kwargs):
        # QA's original value is args[1]; other hooks also receive value second.
        original = args[1]
        if self.used:
            return original
        before = deepcopy(original)
        result = getattr(self.inner, hook)(*args, **kwargs)
        changed = result != before
        self.emit('fault_boundary', hook=hook, mutated=changed,
                  before=asdict(before) if hasattr(before, '__dataclass_fields__') else before,
                  after=asdict(result) if hasattr(result, '__dataclass_fields__') else result)
        if changed:
            self.used = True
        return result

    def on_qa_feedback(self, iteration, feedback, state=None):
        return self.apply('on_qa_feedback', iteration, feedback, state=state)


class _MeteredModel:
    def __init__(self, client, runner):
        self.client, self.runner = client, runner

    def complete(self, system, user):
        return self.runner.call('model', lambda: complete_observed(self.client, system, user),
                                system=system, user=user)


class RecoveryRunner:
    def __init__(self, case, mode, llm, budget):
        if mode not in ('unprotected', 'full_restart', 'always_verify'):
            raise ValueError('Unknown recovery mode')
        self.case, self.mode = case, mode
        self.budget = budget or RunBudget()
        if any((self.budget.model_calls, self.budget.tool_calls, self.budget.verification_calls)):
            raise ValueError('Provide a fresh budget per run')
        self.run_id, self.events, self.attempts = str(uuid4()), [], []
        self.start = perf_counter()
        self.source = source_provenance()
        self.calls, self.recoveries = {}, {}
        self.call_stack = []
        self.artifact_id = None
        self.artifacts = {}
        self.accepted_artifacts = {}
        self.sdk_max_retries = getattr(getattr(llm, '_client', None), 'max_retries', None)
        self.model_config = {key: getattr(llm, key, None) for key in ('model', 'temperature')}
        self.budget_initial = asdict(self.budget)
        self.attempt, self.iteration, self.stage = 0, 0, 'initialization'
        self.last_event = None
        self.llm = _MeteredModel(llm, self) if llm is not None else None
        self.fault = _TransientFault(case, self.emit)

    def emit(self, event, **data):
        event_id = f'{self.run_id}:{len(self.events)+1}'
        elapsed = perf_counter()-self.start
        payload = dict(run_id=self.run_id, attempt_id=self.attempt,
                                event_id=event_id, previous_event_id=self.last_event,
                                stage=self.stage, iteration=self.iteration, event=event,
                                elapsed_seconds=elapsed, elapsed_ms=elapsed*1000)
        payload.update(deepcopy(data))
        self.events.append(payload)
        self.last_event = event_id
        return event_id

    def new_artifact(self, kind):
        self.artifact_id = f'{self.run_id}:artifact:{len(self.artifacts)+1}'
        self.artifacts[self.artifact_id] = dict(kind=kind, attempt_id=self.attempt,
                                               stage=self.stage, source_call_ids=[])
        self.emit('artifact_started', artifact_id=self.artifact_id, kind=kind)
        return self.artifact_id

    def discard(self, ids, reason):
        for call_id in ids:
            call = self.calls[call_id]
            if reason not in call['discarded_reason']:
                call['discarded_reason'].append(reason)
                self.emit('call_discarded', call_id=call_id, discarded_reason=reason,
                          artifact_id=call['artifact_id'])

    def discard_artifact(self, artifact_id, reason):
        if artifact_id:
            self.discard(self.artifacts[artifact_id]['source_call_ids'], reason)

    def recovery_start(self, kind, reason):
        recovery_id = f'{self.run_id}:recovery:{len(self.recoveries)+1}'
        event_id = self.emit('recovery_started', recovery_id=recovery_id,
                             recovery_type=kind, trigger_reason=reason)
        self.recoveries[recovery_id] = dict(recovery_id=recovery_id, recovery_type=kind,
            trigger_reason=reason, attempt_id=self.attempt, stage=self.stage,
            target_attempt_id=self.attempt + (kind == 'full_restart'),
            start_event_id=event_id, start_ms=self.events[-1]['elapsed_ms'],
            end_ms=None, outcome='unresolved', task_quality='UNREVIEWED')
        return recovery_id

    def recovery_end(self, recovery_id, outcome):
        event_id = self.emit('recovery_finished', recovery_id=recovery_id, outcome=outcome)
        self.recoveries[recovery_id].update(end_ms=self.events[-1]['elapsed_ms'],
                                          end_event_id=event_id, outcome=outcome)

    def call(self, kind, fn, **inputs):
        try:
            self.budget.take(kind)
        except BudgetExceeded:
            self.emit('call_blocked', kind=kind)
            raise
        call_id = f'{self.run_id}:call:{len(self.calls)+1}'
        artifact_id = (self.artifact_id if kind != 'verification' and
                       inputs.get('purpose') != 'verification_reference' else None)
        call = dict(call_id=call_id, kind=kind, attempt_id=self.attempt,
                    stage=self.stage, artifact_id=artifact_id, inputs=inputs,
                    output_artifact_id=call_id + ':output',
                    parent_call_id=self.call_stack[-1] if self.call_stack else None,
                    status='incomplete',
                    duration_ms=None, token_usage=None, discarded_reason=[])
        self.calls[call_id] = call
        if artifact_id:
            self.artifacts[artifact_id]['source_call_ids'].append(call_id)
        self.emit('call_started', kind=kind, call_id=call_id, inputs=inputs,
                  artifact_id=artifact_id, parent_call_id=call['parent_call_id'])
        start = perf_counter()
        self.call_stack.append(call_id)
        token = provider_usage_observer.set(lambda usage: call.update(token_usage=usage)) if kind == 'model' else None
        try:
            result = fn()
        except Exception as exc:
            call.update(status='failed', duration_ms=(perf_counter()-start)*1000)
            self.emit('call_failed', **deepcopy(call),
                      duration_seconds=call['duration_ms']/1000, error_type=type(exc).__name__)
            self.discard([call_id], 'execution_failed')
            raise
        finally:
            self.call_stack.pop()
            if token is not None:
                provider_usage_observer.reset(token)
        call.update(status='completed', duration_ms=(perf_counter()-start)*1000)
        payload = asdict(result) if hasattr(result, '__dataclass_fields__') else result
        self.emit('call_completed', **deepcopy(call),
                  duration_seconds=call['duration_ms']/1000, output=payload)
        self.last_call_id = call_id
        return result

    def verify(self, name, fn, artifact_id=None):
        ok, reason = self.call('verification', fn, check=name)
        self.calls[self.last_call_id]['verification_outcome'] = 'accepted' if ok else 'rejected'
        self.last_rejection_reason = reason
        self.emit('verification_decision', check=name, accepted=ok, reason=reason,
                  artifact_id=artifact_id, verification_call_id=self.last_call_id)
        if not ok:
            # The verifier performed useful detection; only its rejected output's
            # producers are discarded, not the successful verification itself.
            if artifact_id:
                producers = self.artifacts[artifact_id]['source_call_ids']
                self.discard([cid for cid in producers if self.calls[cid]['kind'] == 'model'
                              or self.calls[cid]['inputs'].get('purpose') == 'helper'],
                             'verification_rejected')
        return ok

    def check_record(self, issue, result):
        # A fresh read is counted as a business tool call, separately from verification.
        reference = self.call('tool', lambda: services.call_tool(
            issue, case_id=self.case.case_id, user_query=self.case.user_query),
            tool='call_tool', issue=issue, purpose='verification_reference')
        ok = result.status == 'ok' and result.record is not None and result == reference
        return ok, 'record_matches_source' if ok else 'record_unavailable_or_mismatch'

    def check_qa(self, state, feedback):
        unresolved = [i.issue_type for i in state.issues.values()
                      if i.status != IssueStatus.RESOLVED]
        if feedback.passed:
            ok = state.all_resolved() and feedback.missing_issue is None
        else:
            ok = bool(unresolved) and feedback.missing_issue in unresolved
        return ok, 'qa_matches_ledger' if ok else 'qa_ledger_mismatch'

    def helper(self, target, state, accepted):
        route = ISSUE_ROUTE.get(target)
        if route is None:
            raise StageFailure('unroutable_label')
        tries = 2 if self.mode == 'always_verify' else 1
        repair = None
        previous_artifact = None
        for retry in range(tries):
            self.stage = 'helper'
            if retry:
                repair = self.recovery_start('stage_retry', self.last_rejection_reason)
                self.discard_artifact(previous_artifact, 'stage_retry_superseded')
                self.emit('stage_retry', target=target)
            candidate = self.new_artifact('helper_output')
            previous_artifact = candidate
            doc = self.call('tool', lambda: services.retrieve_support_text(target),
                            tool='retrieve_support_text', issue=target)
            doc = self.fault.apply('on_retrieved_text', target, doc)
            result = self.call('tool', lambda: services.call_tool(
                target, case_id=self.case.case_id, user_query=self.case.user_query),
                tool='call_tool', issue=target, purpose='helper')
            result = self.fault.apply('on_tool_call', target, result)
            result = self.fault.apply('on_helper_output', route, result)
            self.emit('helper_candidate', issue=target, record=asdict(result), artifact_id=candidate)
            if self.mode == 'always_verify':
                if not self.verify('helper_record', lambda: self.check_record(target, result), candidate):
                    if retry == 0:
                        continue
                    raise StageFailure('helper_verification_rejected_twice')
            elif result.status != 'ok' or result.record is None:
                if self.mode == 'unprotected':
                    self.emit('helper_unavailable', issue=target, status=result.status)
                    return
                raise StageFailure('helper_' + result.status)
            content = (generate_response(self.llm, target, doc, result.record,
                       user_query=state.user_query, record_authoritative=result.authoritative)
                       if self.llm is not None else str(result.record))
            issue = state.ensure_issue(target)
            issue.attempts += 1
            issue.add_evidence(Evidence('support_doc', doc, False))
            issue.add_evidence(Evidence('billing_service' if route=='billing' else 'technical_tool',
                                       content, result.authoritative))
            if target in self.accepted_artifacts:
                self.discard_artifact(self.accepted_artifacts[target], 'output_replaced')
                self.emit('natural_correction', target=target, policy_triggered=False,
                          outcome='output_replaced', task_quality='UNREVIEWED')
            self.accepted_artifacts[target] = candidate
            accepted[target] = deepcopy(result)
            self.emit('helper_accepted', issue=target, answer=content, record=asdict(result), artifact_id=candidate)
            if repair:
                self.recovery_end(repair, 'accepted')
            return

    def attempt_run(self):
        state = WorkflowState(self.case.case_id, self.case.user_query, self.case.max_iterations)
        accepted = {}
        self.accepted_artifacts = {}
        self.current_state = state
        self.stage, self.iteration = 'classification', 0
        self.new_artifact('classification')
        router = RouterAgent(self.llm)
        router.decompose(state)
        self.emit('classification', issues=list(state.issues))
        if not state.issues or any(i not in ISSUE_ROUTE for i in state.issues):
            raise StageFailure('invalid_classification')
        qa = QAAgent(self.fault, self.llm)
        feedback = None
        for iteration in range(1, self.case.max_iterations + 1):
            state.iteration = self.iteration = iteration
            self.stage = 'router'
            target = router.decide(state, feedback)
            self.emit('router_selection', input=asdict(feedback) if feedback else None,
                      target=target, selected_was_resolved=state.is_resolved(target),
                      unresolved=[i.issue_type for i in state.open_issues()])
            if target is None:
                break
            self.helper(target, state, accepted)
            self.stage = 'qa'
            qa_repair = None
            previous_qa = None
            for retry in range(2 if self.mode == 'always_verify' else 1):
                if retry:
                    qa_repair = self.recovery_start('stage_retry', self.last_rejection_reason)
                    self.discard_artifact(previous_qa, 'stage_retry_superseded')
                    self.emit('stage_retry', target='qa')
                candidate = self.new_artifact('qa_feedback')
                previous_qa = candidate
                feedback = qa.review(state)
                self.emit('qa_candidate', feedback=asdict(feedback), artifact_id=candidate)
                if self.mode != 'always_verify' or self.verify('qa_feedback', lambda: self.check_qa(state, feedback), candidate):
                    if qa_repair:
                        self.recovery_end(qa_repair, 'accepted')
                    break
                if retry:
                    raise StageFailure('qa_verification_rejected_twice')
            if feedback.passed and state.all_resolved():
                break
        if not state.all_resolved():
            raise StageFailure('iteration_budget_exhausted')
        if self.mode == 'full_restart':
            self.stage = 'terminal_validation'
            # Inspect final accepted records, without using case.expected_* or prose gold labels.
            for issue, result in accepted.items():
                if not self.verify('final_record', lambda i=issue, r=result: self.check_record(i, r), self.accepted_artifacts[issue]):
                    raise StageFailure('final_record_mismatch')
        state.final_status = 'resolved'
        return state

    def run(self):
        outcome = 'failed'
        restart_repair = None
        for attempt in range(1, 3 if self.mode == 'full_restart' else 2):
            outcome = 'failed'
            self.attempt, self.iteration, self.stage = attempt, 0, 'attempt'
            before = asdict(self.budget)
            started = perf_counter()
            self.emit('attempt_started', fresh_state=True, fault_disabled=attempt > 1)
            if attempt > 1:
                # Disable even an unactivated schedule: restart tests transient first-attempt faults.
                self.fault.used = True
            error, retryable = None, False
            self.current_state = None
            try:
                self.attempt_run()
                outcome = 'completed'
            except StageFailure as exc:
                error, retryable = str(exc), True
            except BudgetExceeded as exc:
                error = str(exc)
                outcome = 'budget_exhausted'
            except Exception as exc:
                # Provider/configuration errors are recorded, never automatically retried.
                error = type(exc).__name__
                outcome = 'error'
            state = self.current_state
            self.attempts.append(dict(attempt_id=attempt, status=outcome,
                failure_reason=error, iterations=state.iteration if state else 0,
                issue_states={k:v.status.value for k,v in state.issues.items()} if state else {},
                history=deepcopy(state.history) if state else [],
                elapsed_seconds=perf_counter()-started,
                calls={k:getattr(self.budget,k)-before[k] for k in
                       ('model_calls','tool_calls','verification_calls')}))
            self.attempts[-1]['duration_ms'] = self.attempts[-1]['elapsed_seconds']*1000
            self.emit('attempt_finished', status=outcome, failure_reason=error)
            if restart_repair and outcome == 'completed':
                self.recovery_end(restart_repair, 'completed')
            if outcome == 'completed' or not (retryable and self.mode=='full_restart' and attempt==1):
                break
            self.emit('restart_triggered', reason=error)
            restart_repair = self.recovery_start('full_restart', error)
            self.discard([cid for cid, c in self.calls.items()
                          if c['attempt_id'] == attempt and c['artifact_id']],
                         'full_restart_superseded')
        for recovery in self.recoveries.values():
            if recovery['end_ms'] is None:
                recovery['end_event_id'] = self.emit('recovery_finished',
                    recovery_id=recovery['recovery_id'],
                    outcome='failed' if outcome != 'completed' else 'unresolved',
                    measured_through='run_endpoint')
        self.emit('run_finished', status=outcome)
        endpoint = self.events[-1]['elapsed_ms']
        for recovery in self.recoveries.values():
            if recovery['end_ms'] is None:
                recovery.update(end_ms=endpoint, outcome='failed' if outcome != 'completed' else 'unresolved',
                                endpoint_event_id=self.events[-1]['event_id'])
        metrics = summarize(list(self.calls.values()), list(self.recoveries.values()), endpoint)
        return dict(metrics_schema_version=METRICS_SCHEMA_VERSION, metrics=metrics,
                    source_revision=self.source, model_config=self.model_config,
                    sdk_retry_config={'max_retries': self.sdk_max_retries, 'changed': False,
                                      'provider_attempt_count': None,
                                      'semantics': 'Application calls observed; internal SDK attempts unavailable.'},
                    budget_config=self.budget_initial,
                    max_iterations=self.case.max_iterations,
                    budget_semantics='Separate dispatch budgets; tool excludes verification; reference reads consume tool budget.',
                    calls=list(self.calls.values()), artifacts=self.artifacts,
                    recoveries=list(self.recoveries.values()),
                    profile='support-recovery-v1', run_id=self.run_id,
                    case_id=self.case.case_id, mode=self.mode, status=outcome,
                    attempts=self.attempts, events=self.events, budget=asdict(self.budget),
                    restart_count=len(self.attempts)-1,
                    fault_type=self.case.fault_type, fault_config=deepcopy(self.case.fault_config),
                    actual_mutation_count=sum(e.get('mutated', False) for e in self.events),
                    stage_retry_count=sum(e['event']=='stage_retry' for e in self.events),
                    repeated_resolved_routes=sum(e.get('selected_was_resolved', False) for e in self.events),
                    total_iterations=sum(a['iterations'] for a in self.attempts),
                    elapsed_seconds=perf_counter()-self.start,
                    task_quality='UNREVIEWED', recovery_success=None,
                    provider_tokens=None,
                    limitations=['Structural verification does not assess prose quality or classification completeness.',
                                 'Provider usage is observed only for instrumented clients; internal SDK attempts remain unknown.',
                                 'Tools include document retrieval and verification reference reads.'])


def run_recovery_case(case, *, mode='unprotected', llm=None, budget=None):
    return RecoveryRunner(case, mode, llm, budget).run()
