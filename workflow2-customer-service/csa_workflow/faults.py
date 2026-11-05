"""Fault injector.

Intercepts a selected intermediate output *before* the next agent consumes it,
matching the five dataset fault types. The injector is a passive middleware: the
orchestrator routes each stage's output through the matching hook, and the hook
mutates it only when the configured trigger fires.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .services import ToolResult
from .state import IssueStatus, WorkflowState
from .taxonomy import ISSUE_ROUTE

QA_FIRST_MISSING_ONCE_V1 = "qa_first_missing_once_v1"


@dataclass
class QAFeedback:
    passed: bool
    missing_issue: str | None
    reason: str


class FaultInjector:
    def __init__(self, fault_type: str, fault_config: dict | None):
        self.fault_type = fault_type or "none"
        self.cfg = fault_config or {}
        self._cached_feedback: QAFeedback | None = None
        self._helper_corrupted: set[str] = set()
        self.qa_mutation_count = 0
        self.last_profile_event: dict | None = None
        self._resolved_at: dict[str, int] = {}
        self._previous_resolved: set[str] = set()

    def _first_missing_once(self, iteration, feedback, state):
        """Newest observed resolution wins; simultaneous resolutions sort by label.

        Resolution transitions are observed at every QA boundary, after QA's
        normal evidence checks. No labels or state are synthesized or repaired.
        """
        reason = None
        candidates = []
        if state is not None:
            resolved = {label for label, issue in state.issues.items()
                        if issue.status == IssueStatus.RESOLVED}
            for label in resolved - self._previous_resolved:
                self._resolved_at[label] = iteration
            self._previous_resolved = resolved
            candidates = sorted(
                (label for label in resolved if label in ISSUE_ROUTE
                 and label != feedback.missing_issue),
                key=lambda label: (-self._resolved_at[label], label))
        if self.qa_mutation_count:
            reason = "already_injected_once"
        elif self.cfg.get("target_stage") != "qa_to_router":
            reason = "target_stage_mismatch"
        elif state is None:
            reason = "workflow_state_unavailable"
        elif feedback.missing_issue is None:
            reason = "no_missing_issue"
        elif feedback.missing_issue not in ISSUE_ROUTE:
            reason = "invalid_missing_issue_label"
        elif (feedback.missing_issue not in state.issues
              or state.issues[feedback.missing_issue].status != IssueStatus.OPEN):
            reason = "missing_issue_not_unresolved_in_case"
        elif not candidates:
            reason = "no_resolved_replacement_candidate"
        elif iteration >= state.max_iterations:
            reason = "no_remaining_router_iteration"
        replacement = candidates[0] if reason is None else None
        if reason is None:
            self.qa_mutation_count += 1
        self.last_profile_event = dict(
            profile=QA_FIRST_MISSING_ONCE_V1, eligible=reason is None,
            skip_reason=reason, injection_iteration=iteration if reason is None else None,
            original_label=feedback.missing_issue, replacement_label=replacement,
            actual_mutation_count=self.qa_mutation_count,
            resolved_candidates=candidates, resolved_at=dict(self._resolved_at))
        return replace(feedback, missing_issue=replacement) if reason is None else feedback

    # --- timeout: simulated tool exceeds its deadline -------------------
    def on_tool_call(self, issue_type: str, result: ToolResult) -> ToolResult:
        if self.fault_type != "timeout":
            return result
        if self.cfg.get("target_stage") == "simulated_tool":
            return ToolResult("timeout", None, authoritative=result.authoritative)
        return result

    # --- prompt_injection: adversarial content in retrieved text --------
    def on_retrieved_text(self, issue_type: str, text: str) -> str:
        if self.fault_type != "prompt_injection":
            return text
        if self.cfg.get("target_stage") == "retrieved_support_text":
            payload = self.cfg.get("payload", "")
            return f"{text}\n\n[RETRIEVED-DOC] {payload}"
        return text

    # --- helper_corruption: contradictory / unverified helper output ----
    def on_helper_output(self, agent: str, result: ToolResult) -> ToolResult:
        if self.fault_type != "helper_corruption":
            return result
        if self.cfg.get("target_agent") != agent:
            return result
        # Inject once: the corruption is a single intercepted output, so a
        # validated retry obtains clean authoritative evidence and recovers.
        if agent in self._helper_corrupted:
            return result
        self._helper_corrupted.add(agent)
        record = dict(result.record or {})
        record["provenance"] = "unverified"
        record["state"] = "CONTRADICTORY"
        if "amount" in record:
            record["amount"] = round(record["amount"] * 10 + 1, 2)  # implausible value
        return ToolResult("ok", record, authoritative=False)

    # --- qa_corruption: rewrite QA->Router feedback ---------------------
    def on_qa_feedback(self, iteration: int, feedback: QAFeedback,
                       state: WorkflowState | None = None) -> QAFeedback:
        if self.fault_type != "qa_corruption":
            return feedback
        if self.cfg.get("profile") == QA_FIRST_MISSING_ONCE_V1:
            return self._first_missing_once(iteration, feedback, state)
        if self.cfg.get("target_stage") != "qa_to_router":
            return feedback

        # Replay a previously mutated feedback if configured to persist it.
        if self.cfg.get("reuse_mutated_feedback") and self._cached_feedback is not None:
            return self._cached_feedback

        if iteration >= self.cfg.get("trigger_iteration", 2):
            mut = self.cfg.get("mutation", {})
            # A field rewrite must change a real label, not just its reason.
            if (mut.get("field") != "missing_issue"
                    or not isinstance(mut.get("injected"), str)
                    or not mut["injected"]
                    or mut.get("original") == mut["injected"]):
                return feedback
            if feedback.missing_issue == mut.get("original"):
                corrupted = QAFeedback(
                    passed=False,
                    missing_issue=mut.get("injected"),
                    reason=f"[corrupted] {mut.get('field')} rewritten",
                )
                if self.cfg.get("reuse_mutated_feedback"):
                    self._cached_feedback = corrupted
                return corrupted
        return feedback
