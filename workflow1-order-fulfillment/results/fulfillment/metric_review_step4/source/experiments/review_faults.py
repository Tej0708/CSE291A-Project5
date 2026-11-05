"""Offline Step 3 evidence: injection boundaries, clean controls, and saved-response replay."""
import argparse
from collections import deque
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from core.config import Settings
from core.model_client import ModelResult, ModelUsage
from data.loader import DEFAULT_DATASET_PATH
from core.trace import read_trace
from experiments.records import experiment_directory, manifest, save_source, write_json
from experiments.scripted_model import ScriptedModelClient
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.validation import differences
from workflows.fulfillment.workflow import FulfillmentWorkflow


def artifact_values(result):
    return {artifact.stage: artifact.value for artifact in result.artifacts}


def business_state(state):
    # Idempotency keys contain a fresh run ID, so compare the actual business state.
    return {key: value for key, value in state.items() if key != 'idempotency_keys'}


def references_resolve(records):
    seen = set()
    for record in records:
        if not set(record['parent_ids']) <= seen:
            return False
        artifact = record['data'].get('artifact')
        if artifact:
            if not {source['source_id'] for source in artifact['sources']} <= seen:
                return False
            seen.add(artifact['artifact_id'])
        seen.add(record['event_id'])
    return True


def fault_evidence(fault, result, control):
    """Check the actual payload/action or exception boundary, not just a taint label."""
    records, clean_records = read_trace(result.log_path), read_trace(control.log_path)
    injected = [row for row in records if row['event_type'] == 'fault_injected']
    checks = {'activated_once': len(injected) == 1 and result.fault_applied,
              'clean_control_passed': control.check.passed and control.task_check.passed,
              'references_resolve_in_order': references_resolve(records)}
    if len(injected) != 1:
        return {'fault_id': fault.fault_id, 'checks': checks, 'passed': False}
    event = injected[0]
    checks['schedule_matches'] = event['data']['schedule'] == asdict(fault)
    consumers = []
    original = None
    if fault.surface == 'tool_response':
        clean_input = next(row for row in clean_records
                           if row['event_type'] == 'agent_started' and row['stage'] == fault.stage)
        original = clean_input['data']['input']
        if fault.fault_type not in ('timeout', 'malformed_json'):
            tools = [row for row in records if row['event_type'] == 'tool_completed'
                     and event['event_id'] in row['parent_ids']
                     and row['data']['result'] == event['data']['injected']]
            tool_ids = {row['event_id'] for row in tools}
            consumers = [row for row in records if row['event_type'] == 'agent_started'
                         and row['stage'] == fault.stage and tool_ids.intersection(row['parent_ids'])
                         and row['data']['input'] == event['data']['injected']]
    elif fault.surface == 'artifact':
        original = artifact_values(control)[fault.stage]
        overrides = [row for row in records if row['event_type'] == 'artifact_overridden'
                     and event['event_id'] in row['parent_ids']
                     and row['data']['artifact']['value'] == event['data']['injected']]
        for override in overrides:
            artifact = override['data']['artifact']
            for row in records:
                if artifact['artifact_id'] not in row['parent_ids']:
                    continue
                if fault.stage == 'executor_agent':
                    if row['event_type'] == 'tool_started' and row['data']['arguments'] in artifact['value']['actions']:
                        consumers.append(row)
                elif row['event_type'] == 'agent_started':
                    field = {'inventory_agent': 'inventory', 'pricing_agent': 'pricing',
                             'shipping_agent': 'shipping', 'planning_agent': 'plan'}[fault.stage]
                    if row['data']['input'].get(field) == artifact['value']:
                        consumers.append(row)
    else:
        original = next(row['data']['arguments'] for row in clean_records
                        if row['event_type'] == 'tool_started' and row['stage'] == fault.stage)

    if fault.fault_type in ('timeout', 'malformed_json'):
        expected_error = 'TimeoutError' if fault.fault_type == 'timeout' else 'JSONDecodeError'
        consumers = [row for row in records if row['event_type'] == 'tool_failed'
                     and event['event_id'] in row['parent_ids']
                     and row['data']['error_type'] == expected_error]
        checks['controlled_exception_recorded'] = result.error_type == expected_error
        if fault.surface == 'tool_response':
            checks['stopped_before_agent_call'] = not any(row['event_type'] == 'agent_started'
                                                         and row['stage'] == fault.stage for row in records)
        if fault.fault_type == 'timeout':
            checks['configured_delay_observed'] = bool(consumers) and all(
                row['data']['latency_ms'] >= fault.timeout_ms for row in consumers)
        if fault.surface == 'tool_call':
            checks['failed_action_did_not_mutate_state'] = bool(consumers) and all(
                row['data']['before_state'] == row['data']['after_state'] for row in consumers)
    else:
        checks['value_changed'] = event['data']['original'] != event['data']['injected']
    checks['original_matches_clean'] = event['data']['original'] == original
    checks['intended_boundary_observed'] = bool(consumers)
    if fault.fault_class == 'accidental':
        checks['task_impact_demonstrated'] = not result.task_check.passed
    clean_artifacts = artifact_values(control)
    changed = [stage for stage, value in artifact_values(result).items()
               if stage in clean_artifacts and differences(value, clean_artifacts[stage])]
    expected_changes = {
        'F-FUL-01': {'inventory_agent', 'planning_agent', 'executor_agent'},
        'F-FUL-04': {'inventory_agent', 'planning_agent', 'executor_agent'},
        'F-FUL-06': {'pricing_agent', 'planning_agent'},
        'F-FUL-07': {'shipping_agent', 'planning_agent', 'executor_agent'},
        'F-FUL-08': {'planning_agent', 'executor_agent'},
        'F-FUL-09': {'executor_agent'},
    }
    if fault.fault_id in expected_changes:
        checks['expected_artifact_changes_observed'] = expected_changes[fault.fault_id] <= set(changed)
    evidence_type = ('payload_delivery_only' if fault.fault_type == 'prompt_injection' else
                     'controlled_interruption' if fault.fault_type in ('timeout', 'malformed_json') else
                     'changed_result_with_task_impact')
    return {'fault_id': fault.fault_id, 'case_id': fault.case_id, 'fault_type': fault.fault_type,
            'fault_class': fault.fault_class, 'stage': fault.stage, 'surface': fault.surface,
            'fault_event_id': event['event_id'], 'consumer_event_ids': [row['event_id'] for row in consumers],
            'consumer_stages': sorted({row['stage'] for row in consumers}), 'evidence_type': evidence_type,
            'changed_artifact_stages_vs_clean': changed, 'task_passed': result.task_check.passed,
            'run_status': result.run_status, 'error_type': result.error_type,
            'log_path': result.log_path, 'control_log_path': control.log_path,
            'checks': checks, 'passed': all(checks.values())}


class SavedResponseClient:
    """Replay only when prompt, payload, and schema match the saved live request exactly."""
    def __init__(self, records):
        starts = [row for row in records if row['event_type'] == 'agent_started']
        outputs = [row for row in records if row['event_type'] == 'agent_completed']
        if len(starts) != len(outputs) or len(starts) != 5:
            raise ValueError('Replay requires a complete five-agent clean trace')
        self.pending = deque(zip(starts, outputs))
        self.matched_calls = 0

    def generate(self, *, system_prompt, payload, output_schema):
        if not self.pending:
            raise ValueError('Replay requested an extra model call')
        start, output = self.pending.popleft()
        if (start['data']['input'] != payload or start['data']['system_prompt'] != system_prompt
                or start['data']['output_schema'] != output_schema.model_json_schema()):
            raise ValueError('Clean request changed; saved baseline cannot validate this version')
        self.matched_calls += 1
        data = output['data']
        return ModelResult(output_schema.model_validate(data['artifact']['value']),
                           data['raw_model_output'], ModelUsage(), 0.0, 'saved-response-no-api')


def replay_baseline(baseline_dir, log_dir):
    baseline_dir = Path(baseline_dir)
    baseline_manifest = json.loads((baseline_dir / 'manifest.json').read_text())
    if hashlib.sha256(DEFAULT_DATASET_PATH.read_bytes()).hexdigest() != baseline_manifest['dataset_sha256']:
        raise ValueError('Dataset changed since the saved baseline')
    saved = [json.loads(line) for line in (baseline_dir / 'runs.jsonl').read_text().splitlines()]
    if len(saved) != 30 or len({row['task_id'] for row in saved}) != 30:
        raise ValueError('Replay requires the complete 30-order clean baseline')
    rows = []
    for row in saved:
        records = read_trace(row['log_path'])
        client = SavedResponseClient(records)
        result = FulfillmentWorkflow(model_client=client, log_dir=log_dir).run(row['task_id'])
        terminal = records[-1]['data']
        passed = bool(row['passed'] and row['task_passed'] and result.check.passed and result.task_check.passed
                      and result.run_status == 'completed' and not client.pending and client.matched_calls == 5
                      and business_state(result.final_state) == business_state(terminal['final_state']))
        rows.append({'case_id': row['task_id'], 'passed': passed, 'matched_requests': client.matched_calls,
                     'saved_trace': row['log_path'], 'replay_trace': result.log_path})
    return rows


def write_report(destination, summary):
    rows = summary['faults']
    lines = ['# Step 3: offline fault-injection review', '',
             f"Boundary checks passed for {sum(row['passed'] for row in rows)}/{len(rows)} schedules.",
             'No Triton calls, credentials, or network access. Scripted outputs are not live-model robustness results.', '',
             '| Fault | Class | Boundary observed | Evidence | Scripted task correct |',
             '|---|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['fault_id']} | {row['fault_class']} | {', '.join(row['consumer_stages'])} | "
                     f"{row['evidence_type']} | {row['task_passed']} |")
    lines += ['', '## What changed', '',
              '- Invalid stage/surface combinations, unsupported tool-call mutations, invalid paths, and no-op changes are rejected. Failed configuration is never marked as an injected fault or scored as a recovery trial.',
              '- F-FUL-08 now changes shipping_usd to 0 and total_usd to the $25 subtotal. The executor consumes the shipping field and writes the wrong shipment cost. The previous total-only change affected the quote but not downstream actions.',
              '- F-FUL-04 explicitly records a synthetic historical stock value of 5 alongside the old timestamp. It is an augmented stale-snapshot scenario, not observed historical inventory. The original workbook/JSON is unchanged.',
              '', '## Evidence and controls', '',
              '- Three paired clean controls establish successful execution for ORD-1001, ORD-1002, and ORD-1003. summary.json records exact fault and consumer event IDs, payload equality, dependency resolution, and all checks.',
              '- Malformed JSON and the early timeout stop at the inventory tool boundary before an agent receives data. The late timeout occurs after inventory reservation and before shipment creation. These are controlled interruptions, not semantic propagation.',
              '- Both timeout schedules retain the configured 1,500 ms delay in this saved review. Fast unit tests may explicitly replace that delay with zero.',
              '- Prompt injection reaches the scripted inventory input unchanged. The scripted model ignores text instructions by construction; its correct result does not demonstrate that the live model resists the attack.',
              '- Timestamp-only control: the old timestamp is delivered, but all artifacts and task outcome remain correct. This demonstrates why the stale scenario needs an explicitly declared stock-value change.',
              '- Total-only planner control: the incorrect quote reaches the executor, but executor actions and business state remain unchanged. Delivery alone is not proof of downstream behavioral dependence.',
              f"- Saved-response compatibility replay: {sum(row['passed'] for row in summary['baseline_replay'])}/30 orders passed. All 150 prompts, input payloads, and schemas matched the Step 2 requests exactly; final business states also matched. No baseline rerun was billed.",
              '- Original clean-baseline artifacts remain unchanged. manifest.json and source/ preserve this review version, including tests. Fault values and schedules are saved separately from dataset.json.',
              '', '## Limits and next checkpoint', '',
              'The nine accidental scenarios demonstrate task failures under the scripted model; the adversarial scenario demonstrates delivery only. The actual live fault pilot and recovery comparisons remain pending. This review does not estimate live failure rates or validate the propagation/wasted-work metrics.',
              'Next: Step 4, offline validation of propagation and policy-violation metrics. No live experiment is part of that checkpoint.', '',
              'Reproduce with `python -m experiments.review_faults --output-dir <new-directory> --baseline-dir results/fulfillment/clean_baseline_step2`.']
    (destination / 'analysis.md').write_text('\n'.join(lines) + '\n')


def execute_review(destination, baseline_dir):
    # This entry point cannot make a network request, including accidental future additions.
    with patch('socket.socket.connect', side_effect=RuntimeError('Offline review forbids network access')):
        return _execute_review(destination, baseline_dir)


def _execute_review(destination, baseline_dir):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    faults = default_faults()
    cases = sorted({fault.case_id for fault in faults})
    metadata = manifest(Settings('unused', 'unused', 'scripted-no-api', min_request_interval_s=0),
                        cases=cases, repetitions=1, condition='offline_fault_review')
    metadata.update(backend='scripted_and_saved_responses', network_disabled=True,
                    schedules=[asdict(fault) for fault in faults], baseline_dir=str(baseline_dir))
    root = Path(__file__).resolve().parents[1]
    metadata['code_sha256'].update({str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in sorted((root / 'tests').glob('*.py'))})
    write_json(destination / 'manifest.json', metadata)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=destination / 'traces')
    controls = {case: workflow.run(case) for case in cases}
    rows = [fault_evidence(fault, workflow.run(fault.case_id, fault=fault), controls[fault.case_id])
            for fault in faults]
    timestamp = replace(faults[3], fault_id='C-TIMESTAMP-ONLY',
                        changes={'items.0.updated_at': faults[3].changes['items.0.updated_at']})
    total = replace(faults[7], fault_id='C-TOTAL-ONLY', changes={'total_usd': 0})
    timestamp_result = workflow.run(timestamp.case_id, fault=timestamp)
    total_result = workflow.run(total.case_id, fault=total)
    timestamp_events = read_trace(timestamp_result.log_path)
    total_events = read_trace(total_result.log_path)
    negatives = {
        'timestamp_only': {'log_path': timestamp_result.log_path,
            'passed': timestamp_result.fault_applied and timestamp_result.check.passed
                      and timestamp_result.task_check.passed
                      and any(row['event_type'] == 'agent_started' and row['stage'] == 'inventory_agent'
                              and row['data']['input']['items'][0]['updated_at'] == timestamp.changes['items.0.updated_at']
                              for row in timestamp_events)},
        'total_only': {'log_path': total_result.log_path,
            'passed': total_result.fault_applied and not total_result.task_check.passed
                      and artifact_values(total_result)['executor_agent'] == artifact_values(controls[total.case_id])['executor_agent']
                      and business_state(total_result.final_state) == business_state(controls[total.case_id].final_state)
                      and any(row['event_type'] == 'agent_started' and row['stage'] == 'executor_agent'
                              and row['data']['input']['plan']['total_usd'] == 0 for row in total_events)},
    }
    replay = replay_baseline(baseline_dir, destination / 'baseline_replay')
    unchanged = hashlib.sha256(DEFAULT_DATASET_PATH.read_bytes()).hexdigest() == metadata['dataset_sha256']
    summary = {'faults': rows, 'negative_controls': negatives, 'baseline_replay': replay,
               'dataset_unchanged': unchanged,
               'api_usage': {'requests': 0, 'tokens': 0, 'cost_usd': 0},
               'passed': all(row['passed'] for row in rows + replay)
                         and all(row['passed'] for row in negatives.values()) and unchanged}
    write_json(destination / 'summary.json', summary)
    save_source(destination)
    write_report(destination, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--baseline-dir', type=Path, default=Path('results/fulfillment/clean_baseline_step2'))
    args = parser.parse_args()
    summary = execute_review(args.output_dir or experiment_directory('fault_review'), args.baseline_dir)
    print(json.dumps({'passed': summary['passed'], 'fault_schedules': len(summary['faults']),
                      'clean_replays': len(summary['baseline_replay']), 'api_usage': summary['api_usage']}, indent=2))
    return int(not summary['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
