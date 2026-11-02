from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

from core.config import Settings
from core.model_client import TritonModelClient
from workflows.registry import build_workflow

from .metrics import RunMetrics, summarize_trace
from .records import clean_summary, manifest, write_json


@dataclass(frozen=True)
class CleanRunSummary:
    workflow: str
    task_id: str
    run_id: str
    passed: bool
    outcome: str
    log_path: str
    errors: tuple[str, ...]
    metrics: RunMetrics
    run_status: str = "completed"
    failed_stage: str | None = None


def run_clean_workflow(
    *,
    workflow_name: str,
    settings: Settings,
    task_ids: list[str] | None = None,
    repetitions: int = 1,
    output_dir: str | Path | None = None,
    progress: bool = False,
) -> list[CleanRunSummary]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    destination = Path(output_dir) if output_dir is not None else None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=False)
        settings = replace(settings, log_dir=str(destination / 'traces'))
    model_client = TritonModelClient(settings)
    workflow = build_workflow(
        workflow_name,
        model_client=model_client,
        log_dir=settings.log_dir,
    )

    selected_tasks = task_ids or workflow.list_task_ids()
    unknown = set(selected_tasks) - set(workflow.list_task_ids())
    if unknown:
        raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
    if destination is not None:
        write_json(destination / 'manifest.json', manifest(
            settings, cases=selected_tasks, repetitions=repetitions, condition='clean',
        ))
    summaries: list[CleanRunSummary] = []

    for task_id in selected_tasks:
        for _ in range(repetitions):
            result = workflow.run(task_id)
            summaries.append(
                CleanRunSummary(
                    workflow=result.workflow,
                    task_id=task_id,
                    run_id=result.run_id,
                    passed=result.check.passed,
                    outcome=result.outcome,
                    log_path=result.log_path,
                    errors=result.check.errors,
                    metrics=summarize_trace(result.log_path),
                    run_status=result.run_status,
                    failed_stage=result.failed_stage,
                )
            )
            if destination is not None:
                with (destination / 'runs.jsonl').open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(asdict(summaries[-1])) + '\n')
                write_json(destination / 'summary.json', clean_summary(summaries))
            if progress:
                summary = summaries[-1]
                print(f"{task_id}: {summary.run_status} checker_pass={summary.passed} "
                      f"calls={summary.metrics.model_calls} tokens={summary.metrics.total_tokens}", flush=True)

    return summaries
