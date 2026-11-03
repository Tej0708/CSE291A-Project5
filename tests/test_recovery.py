from dataclasses import replace

import pytest

from core.budget import RunBudget
from core.trace import read_trace
from experiments.compare_recovery import trial
from experiments.metrics import summarize_trace
from experiments.propagation import trace_graph
from experiments.scripted_model import ScriptedModelClient
from workflows.fulfillment.faults import default_faults
from workflows.fulfillment.workflow import FulfillmentWorkflow


@pytest.mark.parametrize('mode', ['full_restart', 'always_verify'])
def test_all_clean_cases(mode, tmp_path):
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    for task in workflow.list_task_ids():
        result = workflow.run(task, mode=mode)
        assert result.check.passed, result.check.errors
        assert len(result.attempts) == 1
        metrics = summarize_trace(result.log_path)
        assert metrics.model_calls == 5
        assert metrics.verification_calls == (5 if mode == 'always_verify' else 0)
        assert metrics.incomplete_verification_calls == 0
        trace_graph(read_trace(result.log_path))


@pytest.mark.parametrize('mode', ['full_restart', 'always_verify'])
@pytest.mark.parametrize('fault', default_faults(), ids=lambda fault: fault.fault_id)
def test_fault_recovery(mode, fault, tmp_path):
    fault = replace(fault, timeout_ms=0)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    row = trial(workflow, fault.case_id, mode=mode, fault=fault)
    # Always verify protects agent boundaries, not failed state-changing tools.
    if mode == 'always_verify' and fault.surface == 'tool_call':
        assert row['run_status'] == 'error'
    else:
        assert row['checker_passed'], row
    for attempt in row['attempts']:
        trace_graph(read_trace(attempt['log_path']))
    assert sum(attempt['propagation']['fault_activated'] for attempt in row['attempts']) == 1
    if mode == 'full_restart' and len(row['attempts']) == 2:
        first_metrics = summarize_trace(row['attempts'][0]['log_path'])
        assert row['wasted_work']['discarded_model_calls'] == first_metrics.model_calls


def test_shared_budget_bounds_restart(tmp_path):
    fault = replace(default_faults()[0], timeout_ms=0)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    budget = RunBudget(max_model_calls=5)
    result = workflow.run(fault.case_id, fault=fault, mode='full_restart', budget=budget)
    assert result.error_type == 'BudgetExceeded'
    assert budget.model_calls == 5
    assert len(result.attempts) == 2
    assert result.attempts[0].initial_state == result.attempts[1].initial_state


def test_invalid_fault_is_not_retried(tmp_path):
    fault = replace(default_faults()[0], changes={'items.0.no_such_field': 1})
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    for mode in ('full_restart', 'always_verify'):
        result = workflow.run(fault.case_id, fault=fault, mode=mode)
        assert result.error_type == 'FaultConfigurationError'
        assert len(result.attempts) == 1
        assert not any(row['event_type'] == 'stage_retry' for row in read_trace(result.log_path))


def test_persistent_bad_output_stops_before_actions(tmp_path):
    class WrongInventory(ScriptedModelClient):
        def generate(self, **kwargs):
            result = super().generate(**kwargs)
            if kwargs['output_schema'].__name__ == 'InventoryResult':
                result = replace(result, value=result.value.model_copy(update={
                    'all_items_available': not result.value.all_items_available}))
            return result

    workflow = FulfillmentWorkflow(model_client=WrongInventory(), log_dir=tmp_path)
    result = workflow.run('ORD-1001', mode='always_verify')
    assert result.error_type == 'VerificationError'
    records = read_trace(result.log_path)
    assert sum(row['event_type'] == 'verification_completed' for row in records) == 2
    assert not any(row['event_type'] == 'action_audited' for row in records)


def test_gold_verdict_does_not_trigger_restart(tmp_path, monkeypatch):
    from core.workflow import CheckResult
    from workflows.fulfillment import workflow as module

    real_assess = module.assess_run

    def failed_evaluation(**kwargs):
        check, task_check, stages = real_assess(**kwargs)
        return CheckResult(False, ('evaluation-only failure',)), task_check, stages

    monkeypatch.setattr(module, 'assess_run', failed_evaluation)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    result = workflow.run('ORD-1001', mode='full_restart')
    assert not result.check.passed
    assert not result.recovery_detected
    assert len(result.attempts) == 1


@pytest.mark.parametrize('mode', ['full_restart', 'always_verify'])
def test_programming_errors_are_not_retried(mode, tmp_path):
    class BrokenModel(ScriptedModelClient):
        calls = 0

        def generate(self, **kwargs):
            self.calls += 1
            raise TypeError('implementation defect')

    model = BrokenModel()
    workflow = FulfillmentWorkflow(model_client=model, log_dir=tmp_path)
    result = workflow.run('ORD-1001', mode=mode)
    assert result.error_type == 'TypeError'
    assert model.calls == 1
    assert len(result.attempts) == 1
    assert not any(row['event_type'] == 'stage_retry' for row in read_trace(result.log_path))


@pytest.mark.parametrize('mode', ['unprotected', 'always_verify'])
def test_restart_detector_only_runs_in_restart_mode(mode, tmp_path, monkeypatch):
    from workflows.fulfillment import workflow as module

    def unexpected_detector(*args):
        raise AssertionError('Restart detector should not run for this policy')

    # The checker retains its independent final-state evaluation.
    monkeypatch.setattr(module, 'final_state_errors', unexpected_detector)
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), log_dir=tmp_path)
    result = workflow.run('ORD-1001', mode=mode)
    assert result.check.passed
