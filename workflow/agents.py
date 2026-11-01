"""The four agents in the support loop.

Agents are deterministic (rule-based) so the harness isolates *fault behavior*
rather than model variance. Each method is written so an LLM backend could be
dropped in later without changing the orchestration contract.
"""

from __future__ import annotations

from . import services
from .faults import FaultInjector, QAFeedback
from .llm import LLMClient, classify_issues, generate_response, judge_quality
from .state import Evidence, IssueStatus, WorkflowState
from .taxonomy import ISSUE_KEYWORDS, ISSUE_ROUTE


class RouterAgent:
    """Decomposes the query, then on each turn picks the next issue to route.

    No recovery yet: QA feedback is trusted verbatim. A corrupted
    missing_issue hint is routed as-is, which is exactly how qa_corruption is
    allowed to misdirect the loop.
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def decompose(self, state: WorkflowState) -> None:
        # Model call-site: classify the free-text query into taxonomy issues.
        if self.llm is not None:
            for issue_type in classify_issues(self.llm, state.user_query, list(ISSUE_ROUTE)):
                state.ensure_issue(issue_type)
            if state.issues:
                return
        # Rule-based fallback (keyword cues).
        query = state.user_query.lower()
        for issue_type, cues in ISSUE_KEYWORDS:
            if issue_type in state.issues:
                continue
            if any(cue in query for cue in cues):
                state.ensure_issue(issue_type)

    def decide(self, state: WorkflowState, feedback: QAFeedback | None) -> str | None:
        """Return the issue_type to route next, or None to terminate."""
        if feedback and feedback.missing_issue:
            return feedback.missing_issue
        open_issues = state.open_issues()
        return open_issues[0].issue_type if open_issues else None


class _HelperAgent:
    route: str = ""
    injector: FaultInjector

    def __init__(self, injector: FaultInjector, llm: LLMClient | None = None):
        self.injector = injector
        self.llm = llm

    def handle(self, issue_type: str, state: WorkflowState) -> None:
        issue = state.ensure_issue(issue_type)
        issue.attempts += 1

        # Retrieved text is untrusted data, never instructions.
        doc = self.injector.on_retrieved_text(
            issue_type, services.retrieve_support_text(issue_type)
        )
        issue.add_evidence(Evidence("support_doc", doc, authoritative=False, verified=True))

        # Tool call is subject to timeout / corruption faults.
        result = self.injector.on_tool_call(issue_type, services.call_tool(issue_type))
        result = self.injector.on_helper_output(self.route, result)

        if result.status == "timeout":
            state.log("helper_timeout", issue=issue_type, route=self.route)
            return  # no authoritative evidence recorded; issue stays OPEN

        record = result.record or {}
        # Model call-site: draft the agent's answer from context + tool record.
        if self.llm is not None:
            content = generate_response(self.llm, issue_type, doc, record)
        else:
            content = str(record)
        unverified = record.get("provenance") == "unverified" or record.get("state") == "CONTRADICTORY"
        source = "billing_service" if self.route == "billing" else "technical_tool"
        issue.add_evidence(Evidence(
            source=source,
            content=content,
            authoritative=result.authoritative,
            verified=not unverified,
        ))
        state.log("helper_result", issue=issue_type, route=self.route,
                  verified=not unverified, record=record)


class TechnicalAgent(_HelperAgent):
    route = "technical"


class BillingAgent(_HelperAgent):
    route = "billing"


class QAAgent:
    """Reviews the ledger and marks issues resolved only with real evidence."""

    def __init__(self, injector: FaultInjector, llm: LLMClient | None = None):
        self.injector = injector
        self.llm = llm

    def review(self, state: WorkflowState) -> QAFeedback:
        for issue in state.issues.values():
            if issue.status != IssueStatus.RESOLVED and issue.has_supporting_evidence():
                issue.status = IssueStatus.RESOLVED

        unresolved = [i.issue_type for i in state.issues.values()
                      if i.status != IssueStatus.RESOLVED]
        if not unresolved:
            feedback = QAFeedback(True, None, "all issues resolved with evidence")
        else:
            # Model call-site: judge which unresolved issue to flag next.
            if self.llm is not None:
                missing, reason = judge_quality(self.llm, state.user_query, unresolved)
            else:
                missing, reason = unresolved[0], f"{unresolved[0]} lacks supporting evidence"
            feedback = QAFeedback(False, missing, reason)

        # QA->Router feedback is the qa_corruption injection point.
        return self.injector.on_qa_feedback(state.iteration, feedback)
