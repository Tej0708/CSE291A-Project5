from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import pytest

from core.trace import read_trace
from experiments.metric_cases import RESOURCE_EXPECTED, interleaved_actions, resource_ledger, restart_ledgers, summary_row
from experiments.metrics import summarize_trace
from experiments.propagation import action_metrics, discarded_calls, propagation, trace_graph
from experiments.report import build_summary, write_report
from experiments.scripted_model import ScriptedModelClient
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.models import ExecutionDecision
from workflows.fulfillment.tools import FulfillmentTools
from workflows.fulfillment.workflow import FulfillmentWorkflow


def save(tmp_path, records, name='trace'):
    path = tmp_path / (name + '.jsonl')
    path.write_text(''.join(json.dumps(row) + '\n' for row in records))
    return SimpleNamespace(log_path=str(path))


def test_known_resource_ledger_counts_failures_blocks_unknown_usage_and_overlapping_time(tmp_path):
    result = asdict(summarize_trace(save(tmp_path, resource_ledger()).log_path))
    assert {key: result[key] for key in RESOURCE_EXPECTED} == RESOURCE_EXPECTED


def test_final_rejected_and_failed_calls_count_even_without_successful_retry(tmp_path):
    result = discarded_calls([save(tmp_path, resource_ledger())], 'always_verify')
    assert result['discarded_model_calls'] == 3
    assert result['discarded_tokens'] is None
    assert result['reported_discarded_tokens'] == 17
    assert result['discarded_unknown_usage_calls'] == 2
    assert result['discarded_model_latency_ms'] == 55
    assert result['recomputed_stages'] == result['recomputed_model_calls'] == 1


def test_full_restart_counts_discarded_work_and_only_actual_recomputation(tmp_path):
    attempts = [save(tmp_path, rows, f'attempt-{index}') for index, rows in enumerate(restart_ledgers())]
    result = discarded_calls(attempts, 'full_restart')
    assert result['discarded_model_calls'] == result['recomputed_stages'] == result['recomputed_model_calls'] == 5
    assert result['discarded_tokens'] == result['reported_discarded_tokens'] == 15
    assert result['discarded_model_latency_ms'] == 5


def test_policy_counts_follow_action_identity_not_completion_order():
    records = interleaved_actions()
    trace_graph(records)
    result = action_metrics(records)
    assert result['unauthorized_attempts'] == result['unauthorized_dispatched'] == result['unauthorized_executed'] == 1
    assert result['policy_accounting_complete'] and result['legacy_action_matches'] == 0


def test_duplicate_ignored_does_not_count_as_another_unauthorized_effect():
    result = action_metrics(resource_ledger())
    assert result['unauthorized_attempts'] == result['unauthorized_dispatched'] == 2
    assert result['unauthorized_executed'] == 1


def test_missing_authorization_is_unknown_not_authorized():
    records = interleaved_actions()
    missing = next(row['event_id'] for row in records if row['event_type'] == 'action_audited' and not row['data']['authorized'])
    records = [row for row in records if row['event_id'] != missing]
    for row in records:
        row['parent_ids'] = [value for value in row['parent_ids'] if value != missing]
        if row['data'].get('audit_event_id') == missing:
            del row['data']['audit_event_id']
        if row['event_type'] == 'tool_failed':
            row['data']['before_state'] = None
    result = action_metrics(records)
    assert result['unknown_authorization_actions'] == 1
    assert result['unknown_action_effects'] == 1
    assert not result['policy_accounting_complete']


def test_unauthorized_request_blocked_before_dispatch_has_no_execution():
    records = interleaved_actions()[:4]
    result = action_metrics(records)
    assert result['unauthorized_attempts'] == 1
    assert result['unauthorized_dispatched'] == result['unauthorized_executed'] == 0


def test_incomplete_action_does_not_claim_a_known_outcome():
    result = action_metrics(interleaved_actions()[:5])
    assert result['unauthorized_dispatched'] == 1 and result['unknown_action_effects'] == 1
    assert not result['policy_accounting_complete']


def test_missing_latency_is_not_zero(tmp_path):
    records = resource_ledger()
    next(row for row in records if row['event_type'] == 'agent_completed')['data'].pop('latency_ms')
    assert summarize_trace(save(tmp_path, records).log_path).model_latency_ms is None


@pytest.mark.parametrize('damage', ['missing_parent', 'duplicate_event', 'multiple_faults'])
def test_invalid_dependency_evidence_is_rejected(tmp_path, damage):
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    fault = default_faults()[0]
    result = workflow.run(fault.case_id, fault=fault)
    records = read_trace(result.log_path)
    if damage == 'missing_parent':
        records[-1]['parent_ids'].append('missing')
    elif damage == 'duplicate_event':
        records.append(deepcopy(records[0]))
    else:
        extra = deepcopy(next(row for row in records if row['event_type'] == 'fault_injected'))
        extra['event_id'] = 'another-fault'
        records.append(extra)
    changed = save(tmp_path, records, 'broken')
    with pytest.raises(ValueError):
        propagation(replace(result, log_path=changed.log_path), workflow.dataset)


def test_exposure_and_semantic_error_remain_distinct(tmp_path):
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    fault = default_faults()[5]
    result = workflow.run(fault.case_id, fault=fault)
    effects = propagation(result, workflow.dataset)
    assert effects['dependency_affected_stages'] == ['executor_agent', 'planning_agent', 'pricing_agent']
    assert effects['observed_corrupted_stages'] == ['planning_agent', 'pricing_agent']
    assert effects['tainted_completed_model_calls'] == 3 and effects['corrupted_output_model_calls'] == 2
    assert effects['unauthorized_executed'] == 0
    assert effects['policy_accounting_complete'] and effects['legacy_action_matches'] == 0


def test_real_duplicate_action_is_logged_but_does_not_mutate_again(tmp_path):
    class DuplicateExecutor(ScriptedModelClient):
        def generate(self, **kwargs):
            result = super().generate(**kwargs)
            if kwargs['output_schema'] is ExecutionDecision:
                value = result.value.model_dump(mode='json')
                value['actions'].append(deepcopy(value['actions'][-1]))
                result = replace(result, value=ExecutionDecision.model_validate(value))
            return result
    workflow = FulfillmentWorkflow(model_client=DuplicateExecutor(), log_dir=tmp_path)
    result = workflow.run('ORD-1001')
    effects = propagation(result, workflow.dataset)
    assert effects['unauthorized_attempts'] == effects['unauthorized_dispatched'] == 1
    assert effects['unauthorized_executed'] == 0 and effects['policy_accounting_complete']
    assert summarize_trace(result.log_path).tool_latency_ms is not None


def test_real_failed_action_preserves_and_counts_its_partial_effect(tmp_path, monkeypatch):
    def partial_status_change(self, action, **kwargs):
        self.state.order_status = action.status
        raise RuntimeError('Failure after state change')
    monkeypatch.setattr(FulfillmentTools, 'update_order_status', partial_status_change)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    fault = default_faults()[8]
    result = workflow.run(fault.case_id, fault=fault)
    assert result.run_status == 'error' and result.final_state['order_status'] == 'fulfilled'
    effects = propagation(result, workflow.dataset)
    assert effects['unauthorized_executed'] == 1 and effects['policy_accounting_complete']


def test_instruction_exposure_is_not_automatic_failure_or_waste(tmp_path):
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    fault = default_faults()[4]
    result = workflow.run(fault.case_id, fault=fault)
    effects = propagation(result, workflow.dataset)
    assert effects['delivered_to_agents'] == ['executor_agent', 'inventory_agent', 'planning_agent']
    assert effects['observed_corrupted_stages'] == []
    assert discarded_calls([result], 'unprotected')['discarded_model_calls'] == 0



def test_fault_rate_denominators_require_activation_and_a_valid_control():
    rows = [summary_row('clean'), summary_row('accidental', fault_class='accidental', activated=True, task_passed=False),
            summary_row('adversarial', fault_class='adversarial', activated=True),
            summary_row('not-injected', fault_class='accidental'),
            summary_row('provider', fault_class='accidental', infrastructure=True)]
    rows[1]['initial_propagation']['downstream_corrupted_stages'] = ['planning_agent']
    result = build_summary(rows, 5)
    groups = {row['fault_class']: row for row in result['groups']}
    assert groups['accidental']['runs'] == groups['adversarial']['runs'] == 1
    assert groups['accidental']['downstream_propagation_rate'] == 1
    assert groups['adversarial']['downstream_propagation_rate'] == 0
    assert groups['accidental']['task_success_rate'] == 0 and groups['adversarial']['task_success_rate'] == 1
    assert result['eligible_fault_conditions'] == 2 and result['excluded_fault_conditions'] == 1
    assert result['total_attempted_model_calls'] == 5 and result['reported_tokens_all_attempts'] == 50
    assert result['infrastructure_failure_attempts'] == 1
    rows[0]['checker_passed'] = False
    assert build_summary(rows, 5)['eligible_fault_conditions'] == 0


def test_unknowns_survive_aggregation_and_report_rendering(tmp_path):
    row = summary_row('clean')
    row['policy_accounting_complete'] = False
    row['metrics'].update(model_latency_ms=None, verification_latency_ms=None, total_tokens=None,
                          reported_total_tokens=5, unknown_usage_calls=1)
    result = write_report(tmp_path, [row], {'trials': [{}], 'model': 'offline', 'repetitions': 1})
    group = result['groups'][0]
    assert group['unauthorized_executed'] is None and group['known_unauthorized_executed'] == 0
    assert group['mean_model_latency_ms'] is None and group['total_tokens'] is None
    assert 'unknown' in (tmp_path / 'analysis.md').read_text()
