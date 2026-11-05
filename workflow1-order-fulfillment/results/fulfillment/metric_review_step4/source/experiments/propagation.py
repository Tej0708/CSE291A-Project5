"""Trace-based exposure and observed errors are reported separately."""
from core.trace import read_trace
from experiments.metrics import MODEL_TERMINALS, TOOL_TERMINALS, pair_calls

from workflows.fulfillment.state import FulfillmentState
from workflows.fulfillment.validation import differences, reference_artifacts


def trace_graph(records):
    """Reject broken evidence instead of treating missing edges as no propagation."""
    edges = {}
    for record in records:
        event_id, parents = record['event_id'], set(record.get('parent_ids', []))
        if event_id in edges or not parents <= edges.keys():
            raise ValueError('Duplicate event or unresolved/forward trace parent')
        edges[event_id] = parents
        artifact = record['data'].get('artifact')
        if artifact:
            if artifact['artifact_id'] in edges or not {s['source_id'] for s in artifact['sources']} <= edges.keys():
                raise ValueError('Duplicate artifact or unresolved artifact source')
            edges[artifact['artifact_id']] = {record['event_id']} | {s['source_id'] for s in artifact['sources']}
    return edges


def action_metrics(records):
    """Bind policy decisions to actions, including failures with partial state changes."""
    audits = {row['event_id']: row for row in records if row['event_type'] == 'action_audited'}
    positions = {row['event_id']: index for index, row in enumerate(records)}
    claimed = set()

    def resolve(record):
        explicit = record['data'].get('audit_event_id')
        linked = [key for key in record.get('parent_ids', []) if key in audits]
        if explicit is not None:
            if explicit not in audits or (linked and linked != [explicit]):
                raise ValueError('Unknown or inconsistent action audit link')
            return explicit, False
        if len(linked) == 1:
            return linked[0], False
        if len(linked) > 1:
            raise ValueError('Multiple policy decisions linked to one action')
        # Legacy traces have no action IDs. Accept only one matching earlier audit.
        candidates = [key for key, audit in audits.items() if key not in claimed
                      and positions[key] < positions[record['event_id']]
                      and audit['stage'] == record['stage']
                      and audit['data']['action'] == record['data'].get('arguments')
                      and set(audit['parent_ids']).intersection(record.get('parent_ids', []))]
        return (candidates[0], True) if len(candidates) == 1 else (None, False)

    starts = {}
    for row in records:
        if row['event_type'] == 'tool_started' and row['data'].get('mutates_state'):
            audit_id, legacy = resolve(row)
            starts[row['event_id']] = (audit_id, legacy)
            if audit_id:
                claimed.add(audit_id)
    pairs, pending = pair_calls(records, 'tool_started', TOOL_TERMINALS, 'tool_call_id')
    dispatched = executed = unknown_auth = unknown_effect = legacy_count = 0
    for start, terminal in pairs:
        data = terminal['data']
        if not data.get('mutates_state') and terminal['event_type'] != 'tool_duplicate_ignored':
            continue
        audit_id, legacy = starts.get(start['event_id'], (None, False)) if start else (None, False)
        explicit = data.get('audit_event_id')
        if explicit is not None and audit_id is not None and explicit != audit_id:
            raise ValueError('Tool completion uses a different policy decision from its start')
        if audit_id is None:
            audit_id, legacy = resolve(terminal)
        if audit_id:
            claimed.add(audit_id)
        authorized = audits[audit_id]['data'].get('authorized') if audit_id else None
        dispatched += authorized is False
        unknown_auth += type(authorized) is not bool
        legacy_count += legacy
        if data.get('mutates_state'):
            if data.get('before_state') is None or data.get('after_state') is None:
                unknown_effect += 1
            elif data['before_state'] != data['after_state']:
                executed += authorized is False
    for start in pending:
        if start['data'].get('mutates_state'):
            audit_id, legacy = starts[start['event_id']]
            authorized = audits[audit_id]['data'].get('authorized') if audit_id else None
            dispatched += authorized is False
            unknown_auth += type(authorized) is not bool
            unknown_effect += 1
            legacy_count += legacy
    return {'unauthorized_attempts': sum(row['data'].get('authorized') is False for row in audits.values()),
            'unauthorized_dispatched': dispatched, 'unauthorized_executed': executed,
            'unknown_authorization_actions': unknown_auth, 'unknown_action_effects': unknown_effect,
            'legacy_action_matches': legacy_count,
            'policy_accounting_complete': not (unknown_auth or unknown_effect)}


def propagation(result, dataset):
    records = read_trace(result.log_path)
    roots = {r['event_id'] for r in records if r['event_type'] == 'fault_injected'}
    if len(roots) > 1:
        raise ValueError('Expected at most one injected fault per workflow run')
    edges = trace_graph(records)
    tainted = set(roots)
    while True:
        following = tainted | {node for node, parents in edges.items() if parents & tainted}
        if following == tainted:
            break
        tainted = following
    reference = reference_artifacts(dataset, FulfillmentState.from_dataset(dataset, result.task_id), result.task_id)
    exposed, affected, corrupted = set(), set(), set()
    tainted_calls = corrupted_calls = exposed_calls = 0
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
            corrupted_calls += bool(differences(record['data']['artifact']['value'], reference[record['stage']]))
        if event in ('agent_completed', 'agent_failed') and reachable:
            exposed_calls += 1
    fault_records = [r for r in records if r['event_type'] == 'fault_injected']
    target = fault_records[0]['data']['schedule']['stage'] if fault_records else None
    kind = fault_records[0]['data']['schedule']['fault_type'] if fault_records else None
    expected_error = {'timeout': 'TimeoutError', 'malformed_json': 'JSONDecodeError'}.get(kind)
    interruption = expected_error is not None and any(
        row['event_type'] in ('tool_failed', 'agent_failed') and row['event_id'] in tainted
        and row['data'].get('error_type') == expected_error for row in records)
    return {
        'fault_event_id': next(iter(roots), None),
        'fault_activated': bool(roots),
        'delivered_to_agents': sorted(exposed),
        'dependency_affected_stages': sorted(affected),
        'observed_corrupted_stages': sorted(corrupted),
        'downstream_corrupted_stages': sorted(corrupted - {target}),
        'tainted_completed_model_calls': tainted_calls,
        'exposed_model_calls': exposed_calls,
        'corrupted_output_model_calls': corrupted_calls,
        **action_metrics(records),
        'controlled_interruption': interruption,
        'unrecovered_interruption': interruption and result.run_status == 'error',
    }


def discarded_calls(results, method):
    """Failed, rejected, or superseded calls; exposure alone does not mean wasted work."""
    if method not in ('unprotected', 'full_restart', 'always_verify') or not results:
        raise ValueError('A supported method and at least one run are required')
    discarded, stage_calls = {}, {}
    for index, result in enumerate(results):
        records = read_trace(result.log_path)
        trace_graph(records)
        pairs, _ = pair_calls(records, 'agent_started', MODEL_TERMINALS, 'model_call_id')
        calls = [row for _, row in pairs if row['event_type'] != 'agent_blocked']
        owners = {row['data']['artifact']['artifact_id']: row['event_id'] for row in calls
                  if row['event_type'] == 'agent_completed'}
        rejected = set()
        for row in records:
            if row['event_type'] == 'artifact_overridden':
                prior = [owners[key] for key in row['parent_ids'] if key in owners]
                if len(prior) == 1:
                    owners[row['data']['artifact']['artifact_id']] = prior[0]
            if row['event_type'] == 'verification_completed' and row['data'].get('passed') is False:
                rejected.update(owners[key] for key in row['parent_ids'] if key in owners)
        if method == 'always_verify':
            last = {}
            for row in calls:
                if row['stage'] in last:
                    rejected.add(last[row['stage']])
                last[row['stage']] = row['event_id']
        for row in calls:
            stage_calls[row['stage']] = stage_calls.get(row['stage'], 0) + 1
            if (row['event_type'] == 'agent_failed' or row['event_id'] in rejected
                    or (method == 'full_restart' and index < len(results) - 1)):
                discarded[f"{row['run_id']}:{row['event_id']}"] = row
    tokens = [row['data'].get('usage', {}).get('total_tokens') for row in discarded.values()]
    latencies = [row['data'].get('latency_ms') for row in discarded.values()]
    return {'discarded_model_calls': len(discarded),
            'discarded_tokens': None if any(value is None for value in tokens) else sum(tokens),
            'reported_discarded_tokens': sum(value or 0 for value in tokens),
            'discarded_unknown_usage_calls': sum(any(row['data'].get('usage', {}).get(field) is None
                for field in ('input_tokens', 'output_tokens', 'total_tokens')) for row in discarded.values()),
            'discarded_model_latency_ms': None if any(value is None for value in latencies) else sum(latencies),
            'discarded_call_ids': sorted(discarded),
            'recomputed_stages': sum(count > 1 for count in stage_calls.values()),
            'recomputed_model_calls': sum(max(0, count - 1) for count in stage_calls.values())}
