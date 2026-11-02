"""Run clean controls and fault/recovery comparisons, with resumable records."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import random

from core.config import load_settings
from core.model_client import TritonModelClient
from experiments.records import experiment_directory, manifest, write_json
from experiments.report import latest_trials, write_report
from experiments.trial import METHODS, run_trial
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.workflow import FulfillmentWorkflow


def execute_experiment(*, settings, output_dir, repetitions=1, resume=False,
                       fault_ids=None, methods=METHODS, case_ids=None,
                       max_model_calls=10, max_tool_calls=40, seed=0,
                       model_client=None, faults=None):
    if repetitions < 1 or max_model_calls < 1 or max_tool_calls < 1:
        raise ValueError('Repetitions and budgets must be positive')
    if not set(methods) <= set(METHODS) or not methods:
        raise ValueError('Select at least one valid comparison method')
    destination = Path(output_dir)
    settings = replace(settings, log_dir=str(destination / 'traces'))
    model_client = model_client or TritonModelClient(settings)
    workflow = FulfillmentWorkflow(model_client=model_client, log_dir=settings.log_dir)
    faults = list(default_faults() if faults is None else faults)
    if fault_ids:
        missing = set(fault_ids) - {fault.fault_id for fault in faults}
        if missing:
            raise ValueError(f'Unknown faults: {sorted(missing)}')
        faults = [fault for fault in faults if fault.fault_id in fault_ids]
    cases = sorted(set(case_ids or workflow.list_task_ids()) | {fault.case_id for fault in faults})
    if set(cases) - set(workflow.list_task_ids()):
        raise ValueError('Unknown case ID')
    trials = [{'case_id': case, 'fault_id': None, 'method': 'unprotected', 'repetition': rep}
              for rep in range(1, repetitions + 1) for case in cases]
    comparisons = [{'case_id': fault.case_id, 'fault_id': fault.fault_id, 'method': method, 'repetition': rep}
                   for rep in range(1, repetitions + 1) for fault in faults for method in methods]
    random.Random(seed).shuffle(comparisons)
    trials.extend(comparisons)
    metadata = manifest(settings, cases=cases, repetitions=repetitions, condition='phase1_pilot')
    metadata.update(trials=trials, schedules=[asdict(fault) for fault in faults], seed=seed,
                    max_model_calls=max_model_calls, max_tool_calls=max_tool_calls,
                    backend='injected_test_client' if not isinstance(model_client, TritonModelClient) else 'tritonai')
    rows = []
    if resume:
        previous = json.loads((destination / 'manifest.json').read_text())
        for key in metadata:
            if key != 'started_utc' and metadata[key] != previous.get(key):
                raise ValueError(f'Cannot resume with changed {key}; use a new output directory')
        metadata = previous
        if (destination / 'runs.jsonl').exists():
            rows = [json.loads(line) for line in (destination / 'runs.jsonl').read_text().splitlines() if line]
    else:
        destination.mkdir(parents=True, exist_ok=False)
        write_json(destination / 'manifest.json', metadata)
    done = {row['trial_key'] for row in latest_trials(rows) if not row['infrastructure_failure']}
    by_id = {fault.fault_id: fault for fault in faults}
    for trial in trials:
        key = f"{trial['case_id']}:{trial['fault_id'] or 'clean'}:{trial['method']}:{trial['repetition']}"
        if key in done:
            continue
        row = run_trial(workflow, case_id=trial['case_id'], method=trial['method'],
                        fault=by_id.get(trial['fault_id']), repetition=trial['repetition'],
                        max_model_calls=max_model_calls, max_tool_calls=max_tool_calls)
        rows.append(row)
        with (destination / 'runs.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')
            handle.flush()
        summary = write_report(destination, rows, metadata)
        print(f"{key}: task_pass={row['task_passed']} status={row['run_status']} "
              f"calls={row['metrics']['model_calls']} tokens={row['metrics']['total_tokens']}", flush=True)
        if row['infrastructure_failure']:
            print('Provider failure recorded. Resume this directory after the provider is available.', flush=True)
            return summary
    return write_report(destination, rows, metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--runs', type=int, default=1)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--fault-id', action='append')
    parser.add_argument('--case-id', action='append')
    parser.add_argument('--method', action='append', choices=METHODS)
    parser.add_argument('--max-model-calls', type=int, default=10)
    parser.add_argument('--max-tool-calls', type=int, default=40)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    if args.resume and args.output_dir is None:
        parser.error('--resume requires --output-dir')
    summary = execute_experiment(
        settings=load_settings(), output_dir=args.output_dir or experiment_directory('phase1'),
        repetitions=args.runs, resume=args.resume, fault_ids=args.fault_id,
        case_ids=args.case_id, methods=args.method or METHODS,
        max_model_calls=args.max_model_calls, max_tool_calls=args.max_tool_calls, seed=args.seed,
    )
    print(json.dumps({key: value for key, value in summary.items() if key not in ('groups', 'paired_comparisons')}, indent=2))
    return int(summary['pending_conditions'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
