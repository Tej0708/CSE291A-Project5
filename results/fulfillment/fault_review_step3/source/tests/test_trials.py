from dataclasses import replace
import json

import pytest

from core.config import Settings
from experiments.run_phase1 import execute_experiment
from experiments.trial import run_trial
from test_fulfillment import FakeModelClient
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.workflow import FulfillmentWorkflow


def schedules():
    return [replace(fault, timeout_ms=0) for fault in default_faults()]


def test_full_restart_restores_partial_state_once(tmp_path):
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    fault = schedules()[-1]
    row = run_trial(workflow, case_id=fault.case_id, fault=fault, method='full_restart')
    assert row['task_passed']
    assert len(row['attempts']) == 2
    first, second = row['attempts']
    assert first['final_state']['inventory']['P101']['available_qty'] == 17
    assert second['initial_state']['inventory']['P101']['available_qty'] == 18
    assert second['initial_state']['reservations'] == {}
    assert second['initial_state']['idempotency_keys'] == []
    assert second['final_state']['inventory']['P101']['available_qty'] == 17
    assert row['discarded_model_calls'] == 5
    assert row['recomputed_stages'] == 5
    assert row['recovery_trigger']


def test_recovery_does_not_erase_unauthorized_actions(tmp_path):
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    fault = schedules()[-2]
    row = run_trial(workflow, case_id=fault.case_id, fault=fault, method='full_restart')
    assert row['task_passed']
    assert row['unauthorized_attempts'] == 1
    assert row['unauthorized_executed'] == 1
    protected = run_trial(workflow, case_id=fault.case_id, fault=fault, method='always_verify')
    assert protected['task_passed']
    assert protected['unauthorized_executed'] == 0
    assert protected['metrics']['verification_calls'] > 0


def test_false_stock_has_a_real_dependency_path(tmp_path):
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    fault = schedules()[0]
    row = run_trial(workflow, case_id=fault.case_id, fault=fault)
    propagation = row['initial_propagation']
    assert propagation['delivered_to_agents'] == ['executor_agent', 'inventory_agent', 'planning_agent']
    assert propagation['downstream_corrupted_stages'] == ['executor_agent', 'planning_agent']
    assert 'pricing_agent' not in propagation['dependency_affected_stages']
    assert propagation['unauthorized_attempts'] == 1
    assert propagation['unauthorized_executed'] == 0


def test_restart_cannot_exceed_shared_model_budget(tmp_path):
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    fault = schedules()[0]
    row = run_trial(workflow, case_id=fault.case_id, fault=fault,
                    method='full_restart', max_model_calls=5)
    assert row['metrics']['model_calls'] == 5
    assert row['error_type'] == 'BudgetExceeded'
    assert not row['task_passed']


def test_full_matrix_and_resume_are_reproducible(tmp_path):
    settings = Settings('not-a-key', 'unused', 'scripted')
    destination = tmp_path / 'matrix'
    arguments = dict(settings=settings, output_dir=destination,
                     model_client=FakeModelClient(), faults=schedules())
    summary = execute_experiment(**arguments)
    assert summary['evaluated_conditions'] == summary['planned_conditions'] == 60
    assert summary['all_schedules_activated']
    assert summary['all_fault_conditions_have_valid_controls']
    groups = {(row['fault_class'], row['method']): row for row in summary['groups']}
    assert groups['clean', 'unprotected']['task_successes'] == 30
    assert groups['accidental', 'unprotected']['task_successes'] == 0
    assert groups['accidental', 'full_restart']['task_successes'] == 9
    assert groups['accidental', 'always_verify']['task_successes'] == 9
    before = (destination / 'runs.jsonl').read_bytes()
    execute_experiment(**arguments, resume=True)
    assert before == (destination / 'runs.jsonl').read_bytes()
    with pytest.raises(ValueError, match='changed model'):
        execute_experiment(**{**arguments, 'settings': replace(settings, model_name='different')}, resume=True)
    metadata = json.loads((destination / 'manifest.json').read_text())
    assert 'api_key' not in metadata
    assert (destination / 'analysis.md').exists()
