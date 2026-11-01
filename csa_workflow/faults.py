"""Fault injector.

Intercepts a selected intermediate output *before* the next agent consumes it,
matching the five dataset fault types. The injector is a passive middleware: the
orchestrator routes each stage's output through the matching hook, and the hook
mutates it only when the configured trigger fires.
"""

from __future__ import annotations

from dataclasses import dataclass

from .services import ToolResult


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
    def on_qa_feedback(self, iteration: int, feedback: QAFeedback) -> QAFeedback:
        if self.fault_type != "qa_corruption":
            return feedback
        if self.cfg.get("target_stage") != "qa_to_router":
            return feedback

        # Replay a previously mutated feedback if configured to persist it.
        if self.cfg.get("reuse_mutated_feedback") and self._cached_feedback is not None:
            return self._cached_feedback

        if iteration >= self.cfg.get("trigger_iteration", 2):
            mut = self.cfg.get("mutation", {})
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
