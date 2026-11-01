from __future__ import annotations

from dataclasses import dataclass

from core.config import Settings
from core.model_client import TritonModelClient
from workflows.registry import build_workflow

from .metrics import RunMetrics, summarize_trace


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


def run_clean_workflow(
    *,
    workflow_name: str,
    settings: Settings,
    task_ids: list[str] | None = None,
    repetitions: int = 1,
) -> list[CleanRunSummary]:
    model_client = TritonModelClient(settings)
    workflow = build_workflow(
        workflow_name,
        model_client=model_client,
        log_dir=settings.log_dir,
    )

    selected_tasks = task_ids or workflow.list_task_ids()
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
                )
            )

    return summaries
