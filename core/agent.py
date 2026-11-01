from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from .artifact import AgentArtifact, SourceRef, make_agent_artifact
from .model_client import StructuredModelClient
from .trace import TraceLogger

T = TypeVar("T", bound=BaseModel)


class StructuredAgent:
    """Run one schema-constrained LLM stage and record its agent artifact."""

    def __init__(
        self,
        *,
        workflow: str,
        name: str,
        system_prompt: str,
        output_schema: type[T],
        model_client: StructuredModelClient,
    ) -> None:
        self.workflow = workflow
        self.name = name
        self.system_prompt = system_prompt
        self.output_schema = output_schema
        self.model_client = model_client

    def run(
        self,
        *,
        payload: dict[str, Any],
        logger: TraceLogger,
        sources: list[SourceRef] | None = None,
    ) -> AgentArtifact:
        source_refs = sources or []
        source_ids = [source.source_id for source in source_refs]

        logger.log(
            "agent_started",
            stage=self.name,
            data={"input": payload},
            parent_ids=source_ids,
        )

        try:
            result = self.model_client.generate(
                system_prompt=self.system_prompt,
                payload=payload,
                output_schema=self.output_schema,
            )
        except Exception as exc:
            logger.log(
                "agent_failed",
                stage=self.name,
                data={"error": repr(exc)},
                parent_ids=source_ids,
            )
            raise

        artifact = make_agent_artifact(
            workflow=self.workflow,
            stage=self.name,
            producer_agent=self.name,
            value=result.value,
            sources=source_refs,
        )

        logger.log(
            "agent_completed",
            stage=self.name,
            data={
                "artifact": artifact.model_dump(mode="json"),
                "raw_model_output": result.raw_text,
                "model_name": result.model_name,
                "latency_ms": round(result.latency_ms, 3),
                "usage": {
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "total_tokens": result.usage.total_tokens,
                },
            },
            parent_ids=source_ids,
        )

        return artifact
