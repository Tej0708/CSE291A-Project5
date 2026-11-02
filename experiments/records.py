"""Reproducible experiment metadata. Never copy credentials into results."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from typing import Any
from uuid import uuid4

from core.config import Settings
from data.loader import DEFAULT_DATASET_PATH


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def experiment_directory(kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return Path('results/fulfillment') / f'{kind}_{stamp}_{uuid4().hex[:8]}'


def manifest(settings: Settings, *, cases: list[str], repetitions: int,
             condition: str, dataset_path: Path = DEFAULT_DATASET_PATH) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    files = [root / 'main.py', root / 'requirements.txt']
    for folder in ('core', 'data', 'workflows', 'experiments'):
        files.extend((root / folder).rglob('*.py'))
    versions = {}
    for name in ('openai', 'pydantic', 'python-dotenv'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
        'workflow': 'fulfillment', 'condition': condition,
        'case_ids': cases, 'repetitions': repetitions,
        'model': settings.model_name, 'temperature': 0, 'sdk_max_retries': 0,
        'request_timeout_s': settings.request_timeout_s,
        'min_request_interval_s': settings.min_request_interval_s,
        'max_completion_tokens': settings.max_completion_tokens,
        'python_version': platform.python_version(), 'packages': versions,
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
        'dataset_sha256': hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        'notes': [
            'Each order starts from the same independent inventory snapshot.',
            'Missing provider usage is unknown, never zero.',
            'Latency includes instrumentation, network, and provider time.',
            'No credentials or private endpoint URLs are saved; public price-source URLs may be included.',
        ],
    }


def clean_summary(summaries: list) -> dict[str, Any]:
    metrics = [asdict(row.metrics) for row in summaries]
    tokens = [row['total_tokens'] for row in metrics]
    return {
        'attempted_runs': len(summaries),
        'completed_runs': sum(row.run_status == 'completed' for row in summaries),
        'error_runs': sum(row.run_status == 'error' for row in summaries),
        'checker_passes': sum(row.passed for row in summaries),
        'checker_pass_rate': sum(row.passed for row in summaries) / len(summaries) if summaries else None,
        'task_passes': sum(row.task_passed is True for row in summaries),
        'task_success_rate': sum(row.task_passed is True for row in summaries) / len(summaries) if summaries else None,
        'reported_input_tokens': sum(row['input_tokens'] or 0 for row in metrics),
        'reported_output_tokens': sum(row['output_tokens'] or 0 for row in metrics),
        'model_calls': sum(row['model_calls'] for row in metrics),
        'tool_calls': sum(row['tool_calls'] for row in metrics),
        'total_tokens': None if any(value is None for value in tokens) else sum(tokens),
        'reported_total_tokens': sum(row['reported_total_tokens'] for row in metrics),
        'unknown_usage_calls': sum(row['unknown_usage_calls'] for row in metrics),
        'e2e_latency_ms': sum(row['e2e_latency_ms'] for row in metrics),
    }
