"""Offline recovery matrix. Scripted outcomes validate policy behavior, not LLM robustness."""
import argparse
from dataclasses import asdict, replace
from pathlib import Path

from core.budget import RunBudget
from .metrics import summarize_trace
from .propagation import discarded_calls, propagation
from .records import write_json
from .scripted_model import ScriptedModelClient
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.workflow import FulfillmentWorkflow


def trial(workflow, task_id, *, mode, fault=None, budget=None):
    result = workflow.run(task_id, mode=mode, fault=fault, budget=budget or RunBudget())
    attempts = result.attempts or (result,)
    measured = [asdict(summarize_trace(item.log_path)) for item in attempts]
    metrics = {key: None if any(item[key] is None for item in measured)
               else sum(item[key] for item in measured) for key in measured[0]}
    return {
        'case_id': task_id, 'fault_id': fault.fault_id if fault else None, 'method': mode,
        'checker_passed': result.check.passed, 'task_passed': result.task_check.passed,
        'run_status': result.run_status, 'error_type': result.error_type,
        'recovery_latency_ms': sum(item['e2e_latency_ms'] for item in measured[1:])
                               + sum(item['repair_latency_ms'] for item in measured),
        'metrics': metrics, 'wasted_work': discarded_calls(attempts, mode),
        'attempts': [{'run_id': item.run_id, 'log_path': item.log_path,
                      'recovery_detected': item.recovery_detected,
                      'propagation': propagation(item, workflow.dataset)} for item in attempts],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=destination / 'traces')
    faults = [replace(fault, timeout_ms=0) for fault in default_faults()]
    rows = []
    for task_id in sorted({fault.case_id for fault in faults}):
        for mode in ('unprotected', 'full_restart', 'always_verify'):
            rows.append(trial(workflow, task_id, mode=mode))
    for fault in faults:
        for mode in ('unprotected', 'full_restart', 'always_verify'):
            rows.append(trial(workflow, fault.case_id, mode=mode, fault=fault))
    write_json(destination / 'results.json', {
        'model': 'scripted_offline', 'transient_faults': True, 'trials': rows,
    })


if __name__ == '__main__':
    main()
