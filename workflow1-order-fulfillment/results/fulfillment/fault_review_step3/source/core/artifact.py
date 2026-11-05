from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourceRef(BaseModel):
    """Reference to an input source consumed by an agent artifact."""

    model_config = ConfigDict(frozen=True)

    source_type: Literal["artifact", "tool_event"]
    source_id: str


class AgentArtifact(BaseModel):
    """Structured intermediate result produced by an agent."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow: str
    stage: str
    producer_agent: str
    value: dict[str, Any]
    sources: tuple[SourceRef, ...] = ()
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def artifact_source(artifact: AgentArtifact) -> SourceRef:
    return SourceRef(
        source_type="artifact",
        source_id=artifact.artifact_id,
    )


def tool_event_source(event_id: str) -> SourceRef:
    return SourceRef(
        source_type="tool_event",
        source_id=event_id,
    )


def make_agent_artifact(
    *,
    workflow: str,
    stage: str,
    producer_agent: str,
    value: BaseModel,
    sources: list[SourceRef] | None = None,
) -> AgentArtifact:
    return AgentArtifact(
        workflow=workflow,
        stage=stage,
        producer_agent=producer_agent,
        value=value.model_dump(mode="json"),
        sources=tuple(sources or []),
    )
