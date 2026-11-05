"""One logical trial, with the same resource budget for each comparison method."""
from dataclasses import asdict
import time

from core.budget import RunBudget
from experiments.metrics import summarize_trace
from experiments.propagation import discarded_calls, propagation, read_trace

METHODS = ('unprotected', 'full_restart', 'always_verify')
INFRASTRUCTURE_ERRORS = {'AuthenticationError', 'PermissionDeniedError', 'RateLimitError',
                         'APIConnectionError', 'APITimeoutError', 'InternalServerError'}


def run_trial(workflow, *, case_id, method='unprotected', fault=None,
              repetition=1, max_model_calls=10, max_tool_calls=40):
    if method not in METHODS:
        raise ValueError(f'Unknown method: {method}')
    started = time.perf_counter()
    budget = RunBudget(max_model_calls=max_model_calls, max_tool_calls=max_tool_calls)
    first = workflow.run(case_id, fault=fault, mode='always_verify' if method == 'always_verify' else 'unprotected', budget=budget)
    results = [first]
    first_propagation = propagation(first, workflow.dataset)
    recovery_ms = 0.0
    # The schedule supplies the faulty result's identity to full restart.
    # Recovery is not triggered by the task oracle or by a guessed detector.
    if method == 'full_restart' and first.fault_applied and first.error_type not in INFRASTRUCTURE_ERRORS:
        recovery_started = time.perf_counter()
        results.append(workflow.run(case_id, budget=budget))
        recovery_ms = (time.perf_counter() - recovery_started) * 1000
    elapsed = (time.perf_counter() - started) * 1000
    metrics = [asdict(summarize_trace(row.log_path)) for row in results]
    if method == 'always_verify':
        recovery_ms = sum(row['repair_latency_ms'] for row in metrics)
    total = {}
    for key in metrics[0]:
        values = [row[key] for row in metrics]
        total[key] = None if any(value is None for value in values) else sum(values)
    final = results[-1]
    stage_calls = {}
    for result in results:
        for event in read_trace(result.log_path):
            if event['event_type'] == 'agent_started':
                stage_calls[event['stage']] = stage_calls.get(event['stage'], 0) + 1
    return {
        'trial_key': f'{case_id}:{fault.fault_id if fault else "clean"}:{method}:{repetition}',
        'case_id': case_id, 'fault_id': fault.fault_id if fault else None,
        'fault_class': fault.fault_class if fault else 'clean',
        'fault_type': fault.fault_type if fault else 'none', 'method': method, 'repetition': repetition,
        'initial_task_passed': first.task_check.passed, 'task_passed': final.task_check.passed,
        'checker_passed': final.check.passed, 'run_status': final.run_status,
        'error_type': final.error_type, 'error': final.error,
        'infrastructure_failure': any(r.error_type in INFRASTRUCTURE_ERRORS for r in results),
        'initial_propagation': first_propagation,
        'unauthorized_attempts': sum(propagation(r, workflow.dataset)['unauthorized_attempts'] for r in results),
        'unauthorized_executed': sum(propagation(r, workflow.dataset)['unauthorized_executed'] for r in results),
        'recomputed_stages': sum(max(0, count - 1) for count in stage_calls.values()),
        'recovery_trigger': first_propagation['fault_event_id'] if len(results) > 1 else None,
        'recovery_latency_ms': recovery_ms, 'e2e_latency_ms': elapsed,
        'metrics': total, **discarded_calls(results, method),
        'attempts': [{'run_id': r.run_id, 'log_path': r.log_path,
                      'run_status': r.run_status, 'error_type': r.error_type,
                      'task_passed': r.task_check.passed, 'checker_passed': r.check.passed,
                      'stage_checks': {name: asdict(check) for name, check in r.stage_checks.items()},
                      'initial_state': r.initial_state, 'final_state': r.final_state,
                      'artifacts': {a.stage: a.value for a in r.artifacts}} for r in results],
    }
