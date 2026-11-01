from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelResult:
    value: BaseModel
    raw_text: str
    usage: ModelUsage
    latency_ms: float
    model_name: str


class StructuredModelClient(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        output_schema: type[T],
    ) -> ModelResult:
        ...


class TritonModelClient:
    """Small OpenAI-compatible client wrapper for TritonAI."""

    def __init__(self, settings: Settings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - only hit in misconfigured envs
            raise RuntimeError(
                "The 'openai' package is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self._model_name = settings.model_name
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        output_schema: type[T],
    ) -> ModelResult:
        schema = output_schema.model_json_schema()
        user_content = {
            "input": payload,
            "required_output_schema": schema,
        }

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model_name,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "Return only one valid JSON object matching the provided schema. "
                        "Do not include Markdown fences or extra commentary."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_content),
                },
            ],
        )
        latency_ms = (time.perf_counter() - started) * 1000

        raw_text = response.choices[0].message.content or ""
        parsed = self._parse_json(raw_text)
        value = output_schema.model_validate(parsed)

        usage = getattr(response, "usage", None)
        model_usage = ModelUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

        return ModelResult(
            value=value,
            raw_text=raw_text,
            usage=model_usage,
            latency_ms=latency_ms,
            model_name=self._model_name,
        )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                cleaned = "\n".join(lines[1:-1])
                if cleaned.lstrip().startswith("json"):
                    cleaned = cleaned.lstrip()[4:].lstrip()

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Model response must be a JSON object.")
        return parsed
