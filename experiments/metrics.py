from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunMetrics:
    model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_latency_ms: float
    e2e_latency_ms: float


def summarize_trace(path: str | Path) -> RunMetrics:
    """Aggregate model/tool counts, token usage, and latency from one JSONL trace."""
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        return RunMetrics(0, 0, 0, 0, 0, 0.0, 0.0)

    agent_records = [
        record for record in records if record["event_type"] == "agent_completed"
    ]
    tool_records = [
        record for record in records if record["event_type"] == "tool_completed"
    ]

    input_tokens = sum(
        record["data"].get("usage", {}).get("input_tokens", 0)
        for record in agent_records
    )
    output_tokens = sum(
        record["data"].get("usage", {}).get("output_tokens", 0)
        for record in agent_records
    )
    total_tokens = sum(
        record["data"].get("usage", {}).get("total_tokens", 0)
        for record in agent_records
    )
    model_latency_ms = sum(
        record["data"].get("latency_ms", 0.0)
        for record in agent_records
    )

    started = datetime.fromisoformat(records[0]["timestamp"])
    ended = datetime.fromisoformat(records[-1]["timestamp"])
    e2e_latency_ms = (ended - started).total_seconds() * 1000

    return RunMetrics(
        model_calls=len(agent_records),
        tool_calls=len(tool_records),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_latency_ms=round(model_latency_ms, 3),
        e2e_latency_ms=round(e2e_latency_ms, 3),
    )
