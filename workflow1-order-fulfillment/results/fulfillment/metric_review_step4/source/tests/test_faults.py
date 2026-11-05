from dataclasses import replace
from copy import deepcopy
import json

import pytest

from test_fulfillment import FakeModelClient
from core.trace import TraceLogger, read_trace
from experiments.review_faults import SavedResponseClient, fault_evidence
from workflows.fulfillment.faults import FaultConfigurationError, FaultInjector, FaultSpec, default_faults
from workflows.fulfillment.models import InventoryResult
from workflows.fulfillment.workflow import FulfillmentWorkflow


@pytest.mark.parametrize('fault', default_faults(), ids=lambda value: value.fault_id)
def test_all_fault_schedules_activate_and_reach_their_boundaries(tmp_path, fault):
    fault = replace(fault, timeout_ms=0)
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    control = workflow.run(fault.case_id)
    unprotected = workflow.run(fault.case_id, fault=fault)
    assert unprotected.fault_applied
    evidence = fault_evidence(fault, unprotected, control)
    assert evidence['passed'], evidence['checks']
    if fault.fault_type != 'prompt_injection':
        assert not unprotected.task_check.passed, fault.fault_id
    # The scripted model does not interpret text instructions. Its prompt-
    # injection outcome is deliberately not evidence of live-model robustness.


@pytest.mark.parametrize('path', ['items.0.typo', 'items.99.available_qty',
                                  'items.-1.available_qty', 'items.0.available_qty.value'])
def test_bad_path_does_not_claim_injection_or_mutate_original(tmp_path, path):
    spec = replace(default_faults()[0], changes={path: 999})
    injector = FaultInjector(spec)
    value = {'items': [{'available_qty': 0}]}
    original = deepcopy(value)
    logger = TraceLogger(workflow='fulfillment', task_id=spec.case_id, log_dir=tmp_path)
    parent = logger.log('tool_started')
    with pytest.raises(FaultConfigurationError, match='path does not exist'):
        injector.apply(value, stage=spec.stage, surface=spec.surface, logger=logger, parent_id=parent)
    assert value == original
    assert not injector.applied and injector.event_id is None
    assert not any(row['event_type'] == 'fault_injected' for row in read_trace(logger.path))


def test_noop_is_configuration_error_not_injected_failure(tmp_path):
    spec = replace(default_faults()[0], changes={'items.0.available_qty': 0})
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    result = workflow.run(spec.case_id, fault=spec)
    records = read_trace(result.log_path)
    assert result.error_type == 'FaultConfigurationError'
    assert not result.fault_applied
    assert not any(row['event_type'] in ('fault_injected', 'stage_retry', 'agent_started') for row in records)


def test_unsupported_targets_fail_before_workflow_execution():
    with pytest.raises(FaultConfigurationError, match='stage/surface'):
        replace(default_faults()[0], stage='inventry_agent')
    with pytest.raises(FaultConfigurationError, match='timeout only'):
        replace(default_faults()[0], surface='tool_call', stage='reserve_inventory')


def test_fault_applies_once_only_at_its_target(tmp_path):
    spec = default_faults()[0]
    injector = FaultInjector(spec)
    value = {'items': [{'available_qty': 0}]}
    logger = TraceLogger(workflow='fulfillment', task_id=spec.case_id, log_dir=tmp_path)
    parent = logger.log('tool_started')
    assert injector.apply(value, stage='pricing_agent', surface=spec.surface, logger=logger, parent_id=parent) == value
    assert not injector.applied
    changed = injector.apply(value, stage=spec.stage, surface=spec.surface, logger=logger, parent_id=parent)
    assert changed['items'][0]['available_qty'] == 999
    assert value['items'][0]['available_qty'] == 0
    assert injector.apply(value, stage=spec.stage, surface=spec.surface, logger=logger, parent_id=parent) == value
    assert sum(row['event_type'] == 'fault_injected' for row in read_trace(logger.path)) == 1


def test_injected_event_alone_does_not_prove_prompt_delivery(tmp_path):
    fault = default_faults()[4]
    workflow = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path)
    control = workflow.run(fault.case_id)
    result = workflow.run(fault.case_id, fault=fault)
    assert fault_evidence(fault, result, control)['passed']
    records = read_trace(result.log_path)
    for row in records:
        if row['event_type'] == 'agent_started' and row['stage'] == 'inventory_agent':
            del row['data']['input']['untrusted_instructions']
    tampered = tmp_path / 'missing-consumption.jsonl'
    tampered.write_text(''.join(json.dumps(row) + '\n' for row in records))
    evidence = fault_evidence(fault, replace(result, log_path=str(tampered)), control)
    assert not evidence['passed']
    assert not evidence['checks']['intended_boundary_observed']


def test_saved_response_replay_rejects_a_changed_request(tmp_path):
    control = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path).run('ORD-1001')
    records = read_trace(control.log_path)
    client = SavedResponseClient(records)
    original = next(row for row in records if row['event_type'] == 'agent_started')
    with pytest.raises(ValueError, match='Clean request changed'):
        client.generate(system_prompt='Changed prompt', payload=original['data']['input'], output_schema=InventoryResult)
    assert client.matched_calls == 0


def test_harmless_intermediate_error_is_not_final_task_failure(tmp_path):
    fault = FaultSpec('test-harmless', 'ORD-1001', 'inventory_agent', 'artifact',
                      'incorrect_result', changes={'items.0.available_qty': 19})
    result = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path).run('ORD-1001', fault=fault)
    assert not result.check.passed
    assert result.task_check.passed
    assert not result.stage_checks['inventory_agent'].passed
    assert result.stage_checks['planning_agent'].passed


def test_shipping_metadata_corruption_is_detected(tmp_path):
    fault = FaultSpec('test-shipping', 'ORD-1001', 'shipping_agent', 'artifact',
                      'incorrect_result', changes={'estimated_days': 999, 'max_weight_kg': 999})
    result = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path).run('ORD-1001', fault=fault)
    assert not result.stage_checks['shipping_agent'].passed
    assert len(result.stage_checks['shipping_agent'].errors) == 2
