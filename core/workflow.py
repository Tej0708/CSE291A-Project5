from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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


class Workflow(ABC):
    name: str

    @abstractmethod
    def list_task_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def run(self, task_id: str) -> WorkflowResult:
        raise NotImplementedError
