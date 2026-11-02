"""Persistent workflow state.

The core defense against the loop/recovery faults is a durable, per-issue ledger.
Every expected issue is tracked independently (dataset invariant #1), and nothing
is marked resolved without provenance-tagged evidence (invariants #2 and #3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .taxonomy import route_for


class IssueStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    BLOCKED = "blocked"


@dataclass
class Evidence:
    """A single piece of support information with its trust provenance."""

    source: str                 # e.g. "billing_service", "technical_tool", "support_doc"
    content: str
    authoritative: bool         # True only for simulated systems of record
    verified: bool = True       # False if a fault marked it unverified/contradictory


@dataclass
class IssueState:
    issue_type: str
    route: str
    status: IssueStatus = IssueStatus.OPEN
    attempts: int = 0
    evidence: list[Evidence] = field(default_factory=list)

    def add_evidence(self, ev: Evidence) -> None:
        self.evidence.append(ev)

    def has_supporting_evidence(self) -> bool:
        """Resolution requires at least one tool/service result for this issue.

        Retrieved support docs are context only, never proof. No recovery/
        validation layer yet: a contradictory or unverified tool record still
        counts here, so helper_corruption is intentionally *not* defended.
        """
        return any(
            e.source in ("technical_tool", "billing_service") for e in self.evidence
        )


@dataclass
class WorkflowState:
    case_id: str
    user_query: str
    max_iterations: int
    issues: dict[str, IssueState] = field(default_factory=dict)
    iteration: int = 0
    final_status: str = "open"
    history: list[dict] = field(default_factory=list)

    # --- ledger helpers -------------------------------------------------
    def ensure_issue(self, issue_type: str) -> IssueState:
        if issue_type not in self.issues:
            self.issues[issue_type] = IssueState(issue_type, route_for(issue_type))
        return self.issues[issue_type]

    def open_issues(self) -> list[IssueState]:
        return [i for i in self.issues.values() if i.status == IssueStatus.OPEN]

    def all_resolved(self) -> bool:
        return bool(self.issues) and all(
            i.status == IssueStatus.RESOLVED for i in self.issues.values()
        )

    def is_resolved(self, issue_type: str) -> bool:
        i = self.issues.get(issue_type)
        return i is not None and i.status == IssueStatus.RESOLVED

    def log(self, stage: str, **data) -> None:
        self.history.append({"iteration": self.iteration, "stage": stage, **data})
