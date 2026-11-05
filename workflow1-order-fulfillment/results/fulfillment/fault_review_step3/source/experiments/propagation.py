"""Trace-based exposure and observed errors are reported separately."""
import json
from pathlib import Path

from workflows.fulfillment.state import FulfillmentState
from workflows.fulfillment.validation import differences, reference_artifacts


def read_trace(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def propagation(result, dataset):
    records = read_trace(result.log_path)
    roots = {r['event_id'] for r in records if r['event_type'] == 'fault_injected'}
    edges = {r['event_id']: set(r['parent_ids']) for r in records}
    for record in records:
        artifact = record['data'].get('artifact')
        if artifact:
            edges[artifact['artifact_id']] = {record['event_id']} | {s['source_id'] for s in artifact['sources']}
    tainted = set(roots)
    while True:
        following = tainted | {node for node, parents in edges.items() if parents & tainted}
        if following == tainted:
            break
        tainted = following
    reference = reference_artifacts(dataset, FulfillmentState.from_dataset(dataset, result.task_id), result.task_id)
    exposed, affected, corrupted = set(), set(), set()
    tainted_calls = 0
    unauthorized_attempts = unauthorized_executed = 0
    current_authorized = True
    for record in records:
        event = record['event_type']
        reachable = record['event_id'] in tainted
        if event == 'agent_started' and reachable:
            exposed.add(record['stage'])
        if event in ('agent_completed', 'artifact_overridden') and reachable:
            affected.add(record['stage'])
            if differences(record['data']['artifact']['value'], reference[record['stage']]):
                corrupted.add(record['stage'])
        if event == 'agent_completed' and reachable:
            tainted_calls += 1
        if event == 'action_audited':
            current_authorized = record['data']['authorized']
            unauthorized_attempts += not current_authorized
        if (event == 'tool_completed' and record['data'].get('mutates_state') and not current_authorized
                and record['data']['before_state'] != record['data']['after_state']):
            unauthorized_executed += 1
    fault_records = [r for r in records if r['event_type'] == 'fault_injected']
    target = fault_records[0]['data']['schedule']['stage'] if fault_records else None
    return {
        'fault_event_id': next(iter(roots), None),
        'fault_activated': bool(roots),
        'delivered_to_agents': sorted(exposed),
        'dependency_affected_stages': sorted(affected),
        'observed_corrupted_stages': sorted(corrupted),
        'downstream_corrupted_stages': sorted(corrupted - {target}),
        'tainted_completed_model_calls': tainted_calls,
        'unauthorized_attempts': unauthorized_attempts,
        'unauthorized_executed': unauthorized_executed,
        'controlled_interruption': bool(fault_records and result.run_status == 'error'
                                       and fault_records[0]['data']['schedule']['fault_type'] in ('timeout', 'malformed_json')),
    }


def discarded_calls(results, method):
    """Calls superseded by restart or local retry, including failed attempts."""
    events = [[r for r in read_trace(result.log_path) if r['event_type'] in ('agent_completed', 'agent_failed')]
              for result in results]
    discarded = events[0] if method == 'full_restart' and len(results) > 1 else []
    if method == 'always_verify':
        last_by_stage = {}
        for event in events[0]:
            previous = last_by_stage.get(event['stage'])
            if previous:
                discarded.append(previous)
            last_by_stage[event['stage']] = event
    token_values = [row['data'].get('usage', {}).get('total_tokens') for row in discarded]
    return {'discarded_model_calls': len(discarded),
            'discarded_tokens': None if any(v is None for v in token_values) else sum(token_values)}
