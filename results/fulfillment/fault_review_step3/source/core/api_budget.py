"""Local per-process inference cap; provider key limits remain authoritative."""
from decimal import Decimal
import json

from .model_client import ModelUsage, request_messages


class InferenceBudgetExceeded(RuntimeError):
    api_call_attempted = False


class BudgetedModelClient:
    def __init__(self, client, *, max_calls, max_cost_usd, input_cost_per_token,
                 output_cost_per_token, max_completion_tokens):
        self.client = client
        self.max_calls = max_calls
        self.max_cost = Decimal(str(max_cost_usd))
        self.input_rate = Decimal(str(input_cost_per_token))
        self.output_rate = Decimal(str(output_cost_per_token))
        self.max_completion_tokens = max_completion_tokens
        if (max_calls < 1 or max_completion_tokens < 1 or not self.max_cost.is_finite()
                or self.max_cost <= 0 or any(not rate.is_finite() or rate < 0
                                          for rate in (self.input_rate, self.output_rate))):
            raise ValueError('Invalid API budget or token prices')
        self.calls = 0
        self.estimated_cost = Decimal(0)
        self.reserved_unknown_cost = Decimal(0)
        self.unknown_usage_calls = 0
        self.provider_input_tokens = 0
        self.provider_output_tokens = 0

    def generate(self, *, system_prompt, payload, output_schema):
        messages = request_messages(system_prompt, payload, output_schema)
        # UTF-8 byte count plus a generous framing allowance is a conservative
        # local input estimate, not a provider billing guarantee.
        input_allowance = len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 4096
        reservation = input_allowance * self.input_rate + self.max_completion_tokens * self.output_rate
        if self.calls >= self.max_calls:
            raise InferenceBudgetExceeded('API-call limit reached before sending another request')
        if self.estimated_cost + self.reserved_unknown_cost + reservation > self.max_cost:
            raise InferenceBudgetExceeded('Estimated spend limit reached before sending another request')
        self.calls += 1
        try:
            result = self.client.generate(system_prompt=system_prompt, payload=payload,
                                          output_schema=output_schema)
        except Exception as error:
            self._account(getattr(error, 'usage', ModelUsage()), reservation)
            raise
        self._account(result.usage, reservation)
        return result

    def _account(self, usage, reservation):
        if usage.input_tokens is None or usage.output_tokens is None:
            self.unknown_usage_calls += 1
            self.reserved_unknown_cost += reservation
            return
        if usage.input_tokens < 0 or usage.output_tokens < 0:
            raise ValueError('Provider returned negative token usage')
        self.provider_input_tokens += usage.input_tokens
        self.provider_output_tokens += usage.output_tokens
        self.estimated_cost += (usage.input_tokens * self.input_rate + usage.output_tokens * self.output_rate)

    def budget_snapshot(self):
        return {
            'max_api_calls': self.max_calls, 'max_estimated_cost_usd': float(self.max_cost),
            'max_completion_tokens': self.max_completion_tokens, 'api_calls_sent': self.calls,
            'provider_input_tokens': self.provider_input_tokens,
            'provider_output_tokens': self.provider_output_tokens,
            'estimated_cost_from_reported_usage_usd': float(self.estimated_cost),
            'conservative_reservation_for_unknown_usage_usd': float(self.reserved_unknown_cost),
            'unknown_usage_calls': self.unknown_usage_calls,
            'input_cost_per_token': float(self.input_rate),
            'output_cost_per_token': float(self.output_rate),
        }
