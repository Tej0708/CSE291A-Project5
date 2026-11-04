"""Versioned, evidence-only cost accounting for recovery runs.

Durations overlap: service time, verification time, repair time and wall time
must never be added together. Legacy logs require a separate evidence audit.
"""
import hashlib
import math
from pathlib import Path
import subprocess

METRICS_SCHEMA_VERSION = 'support-cost-v2'
FIELDS = ('input_tokens', 'output_tokens', 'total_tokens')
KINDS = {'model': 'model', 'tool': 'business_tool', 'verification': 'verification'}


def source_provenance():
    root = Path(__file__).resolve().parent.parent
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root,
                                           stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    paths = ('csa_workflow/recovery.py', 'csa_workflow/cost_metrics.py', 'csa_workflow/llm.py', 'csa_workflow/provider_accounting.py')
    return {'git_head': revision, 'file_sha256': {
        name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}}


def _duration(value):
    if value is not None and (not isinstance(value, (int, float)) or
                              not math.isfinite(value) or value < 0):
        raise ValueError('Durations must be finite nonnegative numbers or null')
    return value


def tokens(calls):
    """Reported fields stay separate from derived totals and known subtotals."""
    rows = [c for c in calls if c['kind'] == 'model']
    result = {'unknown_usage_calls': 0, 'incomplete_calls': 0,
              'usage_scope': 'observed_application_responses',
              'underlying_provider_attempt_usage_complete': None}
    values = {f: [] for f in FIELDS}
    derived = []
    for call in rows:
        usage = call.get('token_usage') or {}
        for field in FIELDS:
            value = usage.get(field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Usage must be a nonnegative integer or null')
            values[field].append(value)
        result['unknown_usage_calls'] += any(usage.get(f) is None for f in FIELDS)
        result['incomplete_calls'] += call['status'] == 'incomplete'
        if usage.get('input_tokens') is not None and usage.get('output_tokens') is not None:
            derived.append(usage['input_tokens'] + usage['output_tokens'])
    for field, entries in values.items():
        result['known_' + field] = sum(v for v in entries if v is not None)
        result[field] = (None if result['incomplete_calls'] or any(v is None for v in entries)
                         else sum(entries))
    result['derived_total_tokens_known_subtotal'] = sum(derived)
    result['derived_total_tokens_calls'] = len(derived)
    result['usage_complete'] = not result['unknown_usage_calls'] and not result['incomplete_calls']
    return result


def interval_union(recoveries, endpoint):
    spans = []
    seen = set()
    for recovery in recoveries:
        rid = recovery['recovery_id']
        if rid in seen:
            raise ValueError('Duplicate recovery ID')
        seen.add(rid)
        start = _duration(recovery.get('start_ms'))
        end = _duration(recovery.get('end_ms'))
        if start is None:
            return None
        if end is None:
            end = endpoint
        if end is None:
            return None
        if end < start or (endpoint is not None and end > endpoint):
            raise ValueError('Recovery interval outside recorded run')
        spans.append((start, end))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum(end-start for start, end in merged)


def summarize(calls, recoveries, endpoint):
    """Accept one reconciled record per dispatched call; reject duplicate IDs."""
    if len({c['call_id'] for c in calls}) != len(calls):
        raise ValueError('Duplicate call ID')
    result = {'metrics_schema_version': METRICS_SCHEMA_VERSION,
              'e2e_latency_ms': _duration(endpoint)}
    for call in calls:
        if call['kind'] not in KINDS or call['status'] not in ('completed', 'failed', 'incomplete'):
            raise ValueError('Invalid dispatched call category or status')
    for kind, name in KINDS.items():
        rows = [c for c in calls if c['kind'] == kind]
        terminal = [c for c in rows if c['status'] != 'incomplete']
        durations = [_duration(c.get('duration_ms')) for c in rows]
        result[name + '_calls'] = len(terminal)
        result['started_' + name + '_calls'] = len(rows)
        result['incomplete_' + name + '_calls'] = len(rows)-len(terminal)
        result['failed_' + name + '_calls'] = sum(c['status'] == 'failed' for c in rows)
        result[name + '_latency_ms'] = (None if len(rows) != len(terminal) or
            any(v is None for v in durations) else sum(durations))
        result['known_' + name + '_latency_ms'] = sum(v for v in durations if v is not None)
    result['tool_calls'] = result['business_tool_calls'] + result['verification_calls']
    result['rejected_verification_calls'] = sum(c.get('verification_outcome') == 'rejected' for c in calls)
    result['repair_latency_ms'] = interval_union(recoveries, endpoint)
    result['unresolved_repairs'] = sum(r.get('outcome') == 'unresolved' for r in recoveries)
    result['failed_repairs'] = sum(r.get('outcome') == 'failed' for r in recoveries)
    result['provider_usage'] = tokens(calls)
    discarded = [c for c in calls if c.get('discarded_reason')]
    result['discarded_calls'] = len(discarded)
    result['discarded_categories'] = list(KINDS.values())
    result['discarded_by_kind'] = {name: sum(c['kind'] == kind for c in discarded)
                                   for kind, name in KINDS.items()}
    result['discarded_provider_usage'] = tokens(discarded)
    result['discarded_latency_ms'] = {
        name: (None if any(c.get('duration_ms') is None or c['status'] == 'incomplete'
                          for c in discarded if c['kind'] == kind)
               else sum(c['duration_ms'] for c in discarded if c['kind'] == kind))
        for kind, name in KINDS.items()}
    return result
