from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

from core.config import Settings
from core.model_client import INFRASTRUCTURE_ERRORS, TritonModelClient
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
    attempt_log_paths: tuple[str, ...] = ()
    task_passed: bool | None = None


def run_clean_workflow(
    *,
    workflow_name: str,
    settings: Settings,
    task_ids: list[str] | None = None,
    repetitions: int = 1,
    output_dir: str | Path | None = None,
    progress: bool = False,
    model_client=None,
    budget_metadata: dict | None = None,
    mode: str = "unprotected",
) -> list[CleanRunSummary]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    destination = Path(output_dir) if output_dir is not None else None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=False)
        settings = replace(settings, log_dir=str(destination / 'traces'))
    model_client = model_client if model_client is not None else TritonModelClient(settings)
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
        metadata = manifest(
            settings, cases=selected_tasks, repetitions=repetitions, condition='clean',
        )
        metadata['mode'] = mode
        if budget_metadata is not None:
            metadata['api_budget'] = budget_metadata
        write_json(destination / 'manifest.json', metadata)
    summaries: list[CleanRunSummary] = []

    for task_id in selected_tasks:
        for _ in range(repetitions):
            result = workflow.run(task_id, mode=mode) if workflow_name == 'fulfillment' else workflow.run(task_id)
            attempts = result.attempts or (result,)
            measured = [asdict(summarize_trace(item.log_path)) for item in attempts]
            combined = RunMetrics(**{
                key: None if any(item[key] is None for item in measured)
                else sum(item[key] for item in measured)
                for key in measured[0]
            })
            summaries.append(
                CleanRunSummary(
                    workflow=result.workflow,
                    task_id=task_id,
                    run_id=result.run_id,
                    passed=result.check.passed,
                    outcome=result.outcome,
                    log_path=result.log_path,
                    errors=result.check.errors,
                    metrics=combined,
                    attempt_log_paths=tuple(item.log_path for item in attempts),
                    run_status=result.run_status,
                    failed_stage=result.failed_stage,
                    task_passed=result.task_check.passed if result.task_check else None,
                )
            )
            if destination is not None:
                with (destination / 'runs.jsonl').open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(asdict(summaries[-1])) + '\n')
                summary_data = clean_summary(summaries)
                if hasattr(model_client, 'budget_snapshot'):
                    summary_data['api_budget'] = model_client.budget_snapshot()
                write_json(destination / 'summary.json', summary_data)
            if progress:
                summary = summaries[-1]
                print(f"{task_id}: {summary.run_status} checker_pass={summary.passed} "
                      f"calls={summary.metrics.model_calls} tokens={summary.metrics.total_tokens}", flush=True)
            if result.error_type in INFRASTRUCTURE_ERRORS | {
                'InferenceBudgetExceeded', 'BadRequestError', 'NotFoundError', 'UnprocessableEntityError',
            }:
                return summaries

    return summaries
