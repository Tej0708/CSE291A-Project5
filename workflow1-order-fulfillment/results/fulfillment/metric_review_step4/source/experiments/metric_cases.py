"""Hand-authored accounting fixtures, independent of the workflow/model implementation."""


class Ledger:
    def __init__(self, name):
        self.name, self.rows = name, []

    def add(self, kind, at, stage=None, data=None, parents=()):
        event_id = f'{self.name}-{len(self.rows)}'
        self.rows.append({'event_id': event_id, 'run_id': self.name, 'workflow': 'fulfillment',
                          'task_id': 'ORD-1001', 'event_type': kind, 'stage': stage,
                          'timestamp': '2026-01-01T00:00:00+00:00', 'elapsed_ms': at,
                          'data': data or {}, 'parent_ids': list(parents)})
        return event_id

    def model(self, stage, start, end, *, usage=None, failed=False, blocked=False):
        call = self.add('agent_started', start, stage)
        data = {'model_call_id': call, 'latency_ms': end - start, 'usage': usage or {}}
        if not failed and not blocked:
            data['artifact'] = {'artifact_id': call + '-artifact', 'value': {}, 'sources': []}
        kind = 'agent_blocked' if blocked else 'agent_failed' if failed else 'agent_completed'
        self.add(kind, end, stage, data, [call])
        return call + '-artifact'


def resource_ledger():
    """3 resolved calls + 1 blocked + 1 unresolved; overlapping repairs; partial usage."""
    ledger = Ledger('resources')
    ledger.add('workflow_started', 0)
    artifact = ledger.model('inventory_agent', 10, 30,
                            usage={'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12})
    ledger.model('pricing_agent', 40, 55, failed=True)
    ledger.add('stage_retry', 60, 'pricing_agent')
    ledger.model('pricing_agent', 65, 85, failed=True,
                 usage={'input_tokens': 5, 'output_tokens': None, 'total_tokens': 5})
    ledger.add('stage_retry', 90, 'pricing_agent')
    ledger.model('pricing_agent', 95, 95, blocked=True)
    call = ledger.add('tool_started', 100, 'get_inventory_inputs', {'mutates_state': False})
    ledger.add('tool_completed', 110, 'get_inventory_inputs',
               {'tool_call_id': call, 'latency_ms': 10, 'mutates_state': False}, [call])
    action = {'tool': 'update_order_status', 'status': 'fulfilled'}
    audit = ledger.add('action_audited', 115, action['tool'],
                       {'authorized': False, 'action': action}, [artifact])
    call = ledger.add('tool_started', 120, action['tool'],
                      {'mutates_state': True, 'audit_event_id': audit, 'arguments': action}, [artifact, audit])
    ledger.add('tool_failed', 150, action['tool'],
               {'mutates_state': True, 'tool_call_id': call, 'audit_event_id': audit, 'latency_ms': 30,
                'before_state': {'status': 'pending'}, 'after_state': {'status': 'fulfilled'}}, [call, audit])
    ledger.add('tool_retry', 152, action['tool'])
    audit = ledger.add('action_audited', 155, action['tool'],
                       {'authorized': False, 'action': action}, [artifact])
    call = ledger.add('tool_started', 160, action['tool'],
                      {'mutates_state': True, 'audit_event_id': audit, 'arguments': action}, [artifact, audit])
    ledger.add('tool_duplicate_ignored', 165, action['tool'],
               {'mutates_state': False, 'tool_call_id': call, 'audit_event_id': audit, 'latency_ms': 5}, [call, audit])
    ledger.add('tool_repaired', 168, action['tool'], {'latency_ms': 16})
    ledger.add('verification_started', 170, 'inventory_agent', parents=[artifact])
    ledger.add('verification_completed', 180, 'inventory_agent',
               {'passed': False, 'latency_ms': 10}, [artifact])
    ledger.add('agent_started', 190, 'shipping_agent')
    ledger.add('verification_started', 192, 'shipping_agent')
    ledger.add('tool_started', 195, 'get_shipping_inputs', {'mutates_state': False})
    ledger.add('workflow_completed', 200, data={'run_status': 'error'})
    return ledger.rows


def interleaved_actions():
    """Authorized action finishes before an earlier unauthorized action partially fails."""
    ledger = Ledger('interleaved')
    ledger.add('workflow_started', 0)
    artifact = ledger.model('executor_agent', 1, 2,
                            usage={'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2})
    bad = {'tool': 'update_order_status', 'status': 'fulfilled'}
    good = {'tool': 'update_order_status', 'status': 'rejected_insufficient_stock'}
    audit_bad = ledger.add('action_audited', 10, bad['tool'], {'authorized': False, 'action': bad}, [artifact])
    call_bad = ledger.add('tool_started', 20, bad['tool'],
                          {'mutates_state': True, 'arguments': bad, 'audit_event_id': audit_bad}, [artifact, audit_bad])
    audit_good = ledger.add('action_audited', 30, good['tool'], {'authorized': True, 'action': good}, [artifact])
    call_good = ledger.add('tool_started', 40, good['tool'],
                           {'mutates_state': True, 'arguments': good, 'audit_event_id': audit_good}, [artifact, audit_good])
    ledger.add('tool_completed', 50, good['tool'],
               {'mutates_state': True, 'tool_call_id': call_good, 'audit_event_id': audit_good,
                'latency_ms': 10, 'before_state': {'status': 'pending'},
                'after_state': {'status': good['status']}}, [call_good, audit_good])
    ledger.add('tool_failed', 60, bad['tool'],
               {'mutates_state': True, 'tool_call_id': call_bad, 'audit_event_id': audit_bad,
                'latency_ms': 40, 'before_state': {'status': 'pending'},
                'after_state': {'status': bad['status']}}, [call_bad, audit_bad])
    ledger.add('workflow_completed', 70, data={'run_status': 'error'})
    return ledger.rows


def restart_ledgers():
    rows = []
    for attempt in (1, 2):
        ledger = Ledger(f'restart-{attempt}')
        ledger.add('workflow_started', 0)
        for index, stage in enumerate(('inventory_agent', 'pricing_agent', 'shipping_agent', 'planning_agent', 'executor_agent')):
            ledger.model(stage, 2 * index + 1, 2 * index + 2,
                         usage={'input_tokens': 2, 'output_tokens': 1, 'total_tokens': 3})
        ledger.add('workflow_completed', 12, data={'run_status': 'completed'})
        rows.append(ledger.rows)
    return rows


RESOURCE_EXPECTED = {
    'model_calls': 3, 'failed_model_calls': 2, 'tool_calls': 4, 'failed_tool_calls': 1,
    'input_tokens': None, 'output_tokens': None, 'total_tokens': None,
    'reported_input_tokens': 15, 'reported_output_tokens': 2, 'reported_total_tokens': 17,
    'unknown_usage_calls': 2, 'model_latency_ms': 55, 'tool_latency_ms': 45,
    'verification_calls': 1, 'verification_latency_ms': 10,
    'e2e_latency_ms': 200, 'repair_latency_ms': 140, 'unresolved_repairs': 1,
    'incomplete_model_calls': 1, 'incomplete_tool_calls': 1, 'incomplete_verification_calls': 1,
}


def summary_row(key, *, fault_class='clean', activated=False, task_passed=True, infrastructure=False):
    fault_id = None if fault_class == 'clean' else key
    return {'trial_key': key, 'case_id': 'ORD-1001', 'repetition': 1, 'fault_id': fault_id,
            'fault_class': fault_class, 'method': 'unprotected', 'infrastructure_failure': infrastructure,
            'task_passed': task_passed, 'checker_passed': task_passed, 'run_status': 'completed',
            'attempts': [{'artifacts': {}}], 'unauthorized_attempts': 0, 'unauthorized_executed': 0,
            'policy_accounting_complete': True, 'e2e_latency_ms': 10, 'recovery_latency_ms': 0,
            'recomputed_stages': 0, 'discarded_model_calls': 0, 'discarded_tokens': 0,
            'initial_propagation': {'fault_activated': activated, 'delivered_to_agents': [],
                'dependency_affected_stages': [], 'observed_corrupted_stages': [], 'downstream_corrupted_stages': []},
            'metrics': {'model_calls': 1, 'model_latency_ms': 1, 'tool_calls': 1,
                'verification_calls': 0, 'verification_latency_ms': 0,
                'total_tokens': 10, 'reported_total_tokens': 10, 'unknown_usage_calls': 0}}
