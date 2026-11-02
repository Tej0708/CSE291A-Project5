from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.config import Settings
from core.model_client import ModelCallError, TritonModelClient
from experiments.metrics import summarize_trace
from experiments import run_clean
from test_fulfillment import FakeModelClient
from workflows.fulfillment.models import InventoryResult
from workflows.fulfillment.tools import FulfillmentTools
from workflows.fulfillment.workflow import FulfillmentWorkflow


class FalseStockModel(FakeModelClient):
    def generate(self, *, payload, **kwargs):
        payload = deepcopy(payload)
        if kwargs['output_schema'] is InventoryResult:
            payload['items'][0]['available_qty'] = 999
        return super().generate(payload=payload, **kwargs)


class TimeoutOnceModel(FakeModelClient):
    calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError('simulated timeout')
        return super().generate(**kwargs)


def records(result):
    return [json.loads(line) for line in Path(result.log_path).read_text().splitlines()]


def test_false_stock_preserves_terminal_result_and_failed_tool(tmp_path):
    result = FulfillmentWorkflow(model_client=FalseStockModel(), log_dir=tmp_path).run('ORD-1002')
    assert result.run_status == 'error'
    assert result.failed_stage == 'reserve_inventory'
    assert len(result.artifacts) == 5
    assert result.final_state == result.initial_state
    trace = records(result)
    assert trace[-1]['event_type'] == 'workflow_completed'
    assert trace[-1]['data']['run_status'] == 'error'
    assert any(r['event_type'] == 'tool_failed' for r in trace)
    metrics = summarize_trace(result.log_path)
    assert (metrics.model_calls, metrics.tool_calls, metrics.failed_tool_calls) == (5, 5, 1)


def test_partial_state_survives_later_tool_failure(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError('shipment unavailable')
    monkeypatch.setattr(FulfillmentTools, 'create_shipment', fail)
    result = FulfillmentWorkflow(model_client=FakeModelClient(), log_dir=tmp_path).run('ORD-1001')
    assert result.run_status == 'error'
    assert result.failed_stage == 'create_shipment'
    assert result.final_state['reservations']['ORD-1001']
    assert result.final_state['inventory']['P101']['available_qty'] == 17
    assert result.final_state['shipments'] == {}


def test_timeout_is_counted_and_batch_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(run_clean, 'TritonModelClient', lambda settings: TimeoutOnceModel())
    results = run_clean.run_clean_workflow(
        workflow_name='fulfillment',
        settings=Settings('unused', 'unused', 'fake', str(tmp_path)),
        task_ids=['ORD-1001', 'ORD-1002'],
    )
    assert len(results) == 2
    assert results[0].run_status == 'error'
    assert results[0].metrics.model_calls == 1
    assert results[0].metrics.failed_model_calls == 1
    assert results[0].metrics.total_tokens is None
    assert results[0].metrics.unknown_usage_calls == 1
    assert results[1].passed


def test_invalid_model_json_preserves_response_and_usage():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"broken":'))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=4, total_tokens=24),
    )
    client = TritonModelClient.__new__(TritonModelClient)
    client._model_name = 'fake'
    sent = {}
    def create(**kwargs):
        sent.update(kwargs)
        return response
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(ModelCallError) as error:
        client.generate(system_prompt='test', payload={}, output_schema=InventoryResult)
    assert error.value.raw_text == '{"broken":'
    assert error.value.usage.total_tokens == 24
    assert error.value.latency_ms >= 0
