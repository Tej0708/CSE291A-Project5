"""The support loop orchestrator.

Wires the agents together as a bounded loop:

    Router -> (Technical | Billing) -> QA -> Router -> ...

with the fault injector on the stage boundaries. There is no recovery yet: the
only guard against an infinite loop is the per-case iteration budget. Faults are
free to misdirect, corrupt, time out, or inject content, and the run terminates
either on a genuine QA pass or when the budget is exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .agents import BillingAgent, QAAgent, RouterAgent, TechnicalAgent
from .dataset import Case
from .faults import FaultInjector, QAFeedback
from .llm import LLMClient
from .state import IssueStatus, WorkflowState


@dataclass
class RunResult:
    case_id: str
    final_status: str           # "resolved" | "blocked"
    iterations: int
    issue_states: dict[str, str]
    terminated_by: str          # "qa_pass" | "all_resolved" | "budget_exhausted"
    history: list[dict]

    def matches_expected(self, case: Case) -> bool:
        return self.final_status == case.expected_final_status


def run_case(case: Case, llm: LLMClient | None = None) -> RunResult:
    injector = FaultInjector(case.fault_type, case.fault_config)
    router = RouterAgent(llm)
    helpers = {
        "technical": TechnicalAgent(injector, llm),
        "billing": BillingAgent(injector, llm),
    }
    qa = QAAgent(injector, llm)

    state = WorkflowState(case.case_id, case.user_query, case.max_iterations)
    router.decompose(state)

    feedback: QAFeedback | None = None
    terminated_by = "budget_exhausted"

    while state.iteration < state.max_iterations:
        state.iteration += 1

        target = router.decide(state, feedback)
        if target is None:
            terminated_by = "all_resolved"
            break

        route = state.ensure_issue(target).route
        state.log("route", issue=target, route=route)
        helper = helpers.get(route)
        if helper is None:
            # Router was pointed at an unroutable target (e.g. a corrupted hint).
            state.log("no_helper", issue=target, route=route)
        else:
            helper.handle(target, state)

        feedback = qa.review(state)
        state.log("qa", passed=feedback.passed, missing=feedback.missing_issue,
                  reason=feedback.reason)

        if feedback.passed and state.all_resolved():
            terminated_by = "qa_pass"
            break

    # Honest finalization: resolved only if every issue has real evidence.
    for issue in state.issues.values():
        if issue.status != IssueStatus.RESOLVED:
            issue.status = IssueStatus.BLOCKED
    final_status = "resolved" if state.all_resolved() else "blocked"
    state.final_status = final_status

    return RunResult(
        case_id=case.case_id,
        final_status=final_status,
        iterations=state.iteration,
        issue_states={k: v.status.value for k, v in state.issues.items()},
        terminated_by=terminated_by,
        history=state.history,
    )
