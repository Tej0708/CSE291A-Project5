from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .artifact import AgentArtifact


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowResult:
    workflow: str
    task_id: str
    run_id: str
    outcome: str
    artifacts: tuple[AgentArtifact, ...]
    check: CheckResult
    log_path: str
    run_status: str = "completed"
    failed_stage: str | None = None
    error_type: str | None = None
    error: str | None = None
    initial_state: dict[str, Any] | None = None
    final_state: dict[str, Any] | None = None
    task_check: CheckResult | None = None
    stage_checks: dict[str, CheckResult] = field(default_factory=dict)
    fault_applied: bool = False


class Workflow(ABC):
    name: str

    @abstractmethod
    def list_task_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def run(self, task_id: str) -> WorkflowResult:
        raise NotImplementedError
