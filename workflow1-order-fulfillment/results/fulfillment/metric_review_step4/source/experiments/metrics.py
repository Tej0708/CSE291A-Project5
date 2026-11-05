from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path

from core.trace import read_trace

MODEL_TERMINALS = {'agent_completed', 'agent_failed', 'agent_blocked'}
TOOL_TERMINALS = {'tool_completed', 'tool_failed', 'tool_duplicate_ignored'}


def pair_calls(records, start_type, terminal_types, id_field):
    """Prefer call IDs; accept unambiguous sequential legacy traces only."""
    pending, pairs = {}, []
    for record in records:
        if record['event_type'] == start_type:
            pending[record['event_id']] = record
        elif record['event_type'] in terminal_types:
            call_id = record['data'].get(id_field)
            linked = [value for value in record.get('parent_ids', []) if value in pending]
            if call_id is None and len(linked) == 1:
                call_id = linked[0]
            if call_id is not None:
                if call_id not in pending:
                    raise ValueError(f'Unknown or duplicate call completion: {call_id}')
                start = pending.pop(call_id)
                if start['stage'] != record['stage']:
                    raise ValueError('Call completion stage differs from its start')
            else:
                candidates = [key for key, value in pending.items() if value['stage'] == record['stage']]
                if len(candidates) > 1:
                    raise ValueError('Ambiguous legacy call completion; explicit call IDs required')
                start = pending.pop(candidates[0]) if candidates else None
            pairs.append((start, record))
    return pairs, list(pending.values())


def _sum_latency(records):
    values = [row['data'].get('latency_ms') for row in records]
    if any(value is None for value in values):
        return None
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Invalid recorded latency')
    return round(sum(values), 3)


def _timing(records):
    first = datetime.fromisoformat(records[0]['timestamp'])
    offsets = [row.get('elapsed_ms') if row.get('elapsed_ms') is not None else
               (datetime.fromisoformat(row['timestamp']) - first).total_seconds() * 1000 for row in records]
    if any(not math.isfinite(value) or value < 0 for value in offsets) or offsets != sorted(offsets):
        raise ValueError('Trace times must be finite, nonnegative, and monotonic')
    pending, spans = {}, []
    for record, offset in zip(records, offsets):
        kind = record['event_type']
        key = (kind.split('_')[0], record['stage'])
        if kind in ('stage_retry', 'tool_retry'):
            pending.setdefault(key, offset)
        elif kind in ('stage_repaired', 'tool_repaired') and key in pending:
            spans.append((pending.pop(key), offset))
    # Failed retries still consumed time. Count through the recorded run endpoint.
    spans.extend((start, offsets[-1]) for start in pending.values())
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return round(offsets[-1], 3), round(sum(end - start for start, end in merged), 3), len(pending)


@dataclass(frozen=True)
class RunMetrics:
    model_calls: int
    tool_calls: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model_latency_ms: float | None
    e2e_latency_ms: float
    failed_model_calls: int = 0
    failed_tool_calls: int = 0
    unknown_usage_calls: int = 0
    reported_total_tokens: int = 0
    verification_calls: int = 0
    verification_latency_ms: float | None = 0.0
    repair_latency_ms: float = 0.0
    tool_latency_ms: float | None = 0.0
    reported_input_tokens: int = 0
    reported_output_tokens: int = 0
    incomplete_model_calls: int = 0
    incomplete_tool_calls: int = 0
    incomplete_verification_calls: int = 0
    unresolved_repairs: int = 0


def summarize_trace(path: str | Path) -> RunMetrics:
    """Aggregate model/tool counts, token usage, and latency from one JSONL trace."""
    records = read_trace(path)
    if not records:
        raise ValueError('Cannot summarize an empty trace')
    agents, pending_agents = pair_calls(records, 'agent_started', MODEL_TERMINALS, 'model_call_id')
    tools, pending_tools = pair_calls(records, 'tool_started', TOOL_TERMINALS, 'tool_call_id')
    agent_records = [record for _, record in agents if record['event_type'] != 'agent_blocked']
    tool_records = [record for _, record in tools]
    verification_records = [r for r in records if r['event_type'] == 'verification_completed']
    _, pending_verifications = pair_calls(records, 'verification_started',
                                          {'verification_completed', 'verification_failed'}, 'verification_call_id')

    def token_values(field):
        values = [r['data'].get('usage', {}).get(field) for r in agent_records]
        if any(value is not None and (type(value) is not int or value < 0) for value in values):
            raise ValueError('Token counts must be nonnegative integers or unknown')
        return values

    def token_sum(field: str) -> int | None:
        values = token_values(field)
        return None if any(v is None for v in values) else sum(values)

    input_tokens, output_tokens, total_tokens = (
        token_sum(field) for field in ("input_tokens", "output_tokens", "total_tokens")
    )
    e2e_latency_ms, repair_latency_ms, unresolved_repairs = _timing(records)

    return RunMetrics(
        model_calls=len(agent_records),
        tool_calls=len(tool_records) + len(verification_records),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_latency_ms=_sum_latency(agent_records),
        e2e_latency_ms=round(e2e_latency_ms, 3),
        failed_model_calls=sum(r["event_type"] == "agent_failed" for r in agent_records),
        failed_tool_calls=sum(r["event_type"] == "tool_failed" for r in tool_records),
        unknown_usage_calls=sum(any(r['data'].get('usage', {}).get(field) is None
                                   for field in ('input_tokens', 'output_tokens', 'total_tokens')) for r in agent_records),
        reported_total_tokens=sum(r["data"].get("usage", {}).get("total_tokens") or 0 for r in agent_records),
        verification_calls=len(verification_records),
        verification_latency_ms=_sum_latency(verification_records),
        repair_latency_ms=repair_latency_ms,
        tool_latency_ms=_sum_latency(tool_records),
        reported_input_tokens=sum(value or 0 for value in token_values('input_tokens')),
        reported_output_tokens=sum(value or 0 for value in token_values('output_tokens')),
        incomplete_model_calls=len(pending_agents), incomplete_tool_calls=len(pending_tools),
        incomplete_verification_calls=len(pending_verifications), unresolved_repairs=unresolved_repairs,
    )
