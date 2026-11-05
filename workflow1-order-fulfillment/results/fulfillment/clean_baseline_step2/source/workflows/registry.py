from __future__ import annotations

from pathlib import Path
from typing import Callable

from core.model_client import StructuredModelClient
from core.workflow import Workflow

from .fulfillment import FulfillmentWorkflow

WorkflowFactory = Callable[[StructuredModelClient, str | Path], Workflow]


def _build_fulfillment(
    model_client: StructuredModelClient,
    log_dir: str | Path,
) -> Workflow:
    return FulfillmentWorkflow(model_client=model_client, log_dir=log_dir)


WORKFLOW_FACTORIES: dict[str, WorkflowFactory] = {
    "fulfillment": _build_fulfillment,
}


def list_workflow_names() -> list[str]:
    return sorted(WORKFLOW_FACTORIES)


def build_workflow(
    name: str,
    *,
    model_client: StructuredModelClient,
    log_dir: str | Path,
) -> Workflow:
    try:
        factory = WORKFLOW_FACTORIES[name]
    except KeyError as exc:
        choices = ", ".join(list_workflow_names())
        raise ValueError(f"Unknown workflow {name!r}. Available: {choices}") from exc
    return factory(model_client, log_dir)
