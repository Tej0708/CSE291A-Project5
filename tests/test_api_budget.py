from dataclasses import replace
from decimal import Decimal

import pytest

from core.api_budget import BudgetedModelClient, InferenceBudgetExceeded
from core.model_client import ModelCallError, ModelUsage
from experiments.metrics import summarize_trace
from test_fulfillment import FakeModelClient
from workflows.fulfillment.models import InventoryResult
from workflows.fulfillment.workflow import FulfillmentWorkflow


class MeteredModel(FakeModelClient):
    calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        result = super().generate(**kwargs)
        return replace(result, usage=ModelUsage(100, 50, 150))


def guarded(client, **overrides):
    settings = dict(max_calls=5, max_cost_usd=0.05, input_cost_per_token=0.00000015,
                    output_cost_per_token=0.0000005, max_completion_tokens=1024)
    return BudgetedModelClient(client, **{**settings, **overrides})


def generate(client):
    return client.generate(system_prompt='test', payload={'items': []}, output_schema=InventoryResult)


def test_call_limit_blocks_before_network_dispatch():
    model = MeteredModel()
    client = guarded(model, max_calls=1)
    generate(client)
    with pytest.raises(InferenceBudgetExceeded):
        generate(client)
    assert model.calls == client.calls == 1
    assert client.estimated_cost == Decimal('0.00004000')


def test_spend_limit_blocks_before_first_call():
    model = MeteredModel()
    client = guarded(model, max_cost_usd=0.00000001)
    with pytest.raises(InferenceBudgetExceeded):
        generate(client)
    assert model.calls == client.calls == 0


def test_unknown_usage_reserves_cost_instead_of_counting_zero():
    class FailingModel:
        def generate(self, **kwargs):
            raise ModelCallError(error_type='RateLimitError', latency_ms=1, model_name='fake')
    client = guarded(FailingModel())
    with pytest.raises(ModelCallError):
        generate(client)
    assert client.calls == client.unknown_usage_calls == 1
    assert client.reserved_unknown_cost > 0
    assert client.estimated_cost == 0


def test_guard_rejection_is_not_counted_as_an_api_call(tmp_path):
    model = MeteredModel()
    result = FulfillmentWorkflow(model_client=guarded(model, max_calls=1), log_dir=tmp_path).run('ORD-1001')
    assert result.run_status == 'error'
    assert result.error_type == 'InferenceBudgetExceeded'
    assert summarize_trace(result.log_path).model_calls == model.calls == 1


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -1])
def test_invalid_prices_are_rejected(price):
    with pytest.raises(ValueError):
        guarded(MeteredModel(), input_cost_per_token=price)
