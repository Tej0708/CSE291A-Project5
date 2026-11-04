"""Observe provider responses without editing the frozen model implementation."""
from contextvars import ContextVar
from copy import copy
from types import SimpleNamespace

from .llm import OpenAIClient

provider_usage_observer = ContextVar('recovery_provider_usage_observer', default=None)


def complete_observed(client, system, user):
    """Delegate the original method through a response-observing SDK proxy.

    Only the known OpenAIClient.complete boundary is adapted. Custom methods
    keep their original behavior and unknown usage. The shallow client copy
    shares the real SDK transport, including its unmodified automatic retries.
    No credentials, headers, or SDK object representations enter the log.
    """
    if type(client).complete is not OpenAIClient.complete:
        return client.complete(system, user)
    create = client._client.chat.completions.create

    def observed_create(*args, **kwargs):
        response = create(*args, **kwargs)
        observer = provider_usage_observer.get()
        if observer is not None:
            usage = getattr(response, 'usage', None)
            observer({name: getattr(usage, field, None) for name, field in (
                ('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens'),
                ('total_tokens', 'total_tokens'))})
        return response

    observed = copy(client)
    observed._client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=observed_create)))
    return observed.complete(system, user)
