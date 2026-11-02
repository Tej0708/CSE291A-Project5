from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunMetrics:
    model_calls: int
    tool_calls: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model_latency_ms: float
    e2e_latency_ms: float
    failed_model_calls: int = 0
    failed_tool_calls: int = 0
    unknown_usage_calls: int = 0
    reported_total_tokens: int = 0


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
        record for record in records if record["event_type"] in ("agent_completed", "agent_failed")
    ]
    tool_records = [
        record for record in records if record["event_type"] in ("tool_completed", "tool_failed", "tool_duplicate_ignored")
    ]

    def token_sum(field: str) -> int | None:
        values = [r["data"].get("usage", {}).get(field) for r in agent_records]
        return None if any(v is None for v in values) else sum(values)

    input_tokens, output_tokens, total_tokens = (
        token_sum(field) for field in ("input_tokens", "output_tokens", "total_tokens")
    )
    model_latency_ms = sum(
        record["data"].get("latency_ms", 0.0)
        for record in agent_records
    )

    started = datetime.fromisoformat(records[0]["timestamp"])
    ended = datetime.fromisoformat(records[-1]["timestamp"])
    e2e_latency_ms = records[-1].get("elapsed_ms", (ended - started).total_seconds() * 1000)

    return RunMetrics(
        model_calls=len(agent_records),
        tool_calls=len(tool_records),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_latency_ms=round(model_latency_ms, 3),
        e2e_latency_ms=round(e2e_latency_ms, 3),
        failed_model_calls=sum(r["event_type"] == "agent_failed" for r in agent_records),
        failed_tool_calls=sum(r["event_type"] == "tool_failed" for r in tool_records),
        unknown_usage_calls=sum(r["data"].get("usage", {}).get("total_tokens") is None for r in agent_records),
        reported_total_tokens=sum(r["data"].get("usage", {}).get("total_tokens") or 0 for r in agent_records),
    )
