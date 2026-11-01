"""Issue taxonomy shared by every agent.

The dataset uses exactly ten issue types routed to two helper agents. Keeping the
mapping in one place lets the Router, the helpers, and QA agree on routing and on
what counts as authoritative evidence.
"""

from __future__ import annotations

# issue_type -> helper route
ISSUE_ROUTE: dict[str, str] = {
    # technical route
    "installation_failure": "technical",
    "login_failure": "technical",
    "password_reset": "technical",
    "app_crash": "technical",
    "sync_failure": "technical",
    # billing route
    "subscription_status": "billing",
    "charge_after_cancellation": "billing",
    "duplicate_charge": "billing",
    "incorrect_invoice": "billing",
    "refund_status": "billing",
}

TECHNICAL_ISSUES = {i for i, r in ISSUE_ROUTE.items() if r == "technical"}
BILLING_ISSUES = {i for i, r in ISSUE_ROUTE.items() if r == "billing"}

# Keyword cues the Router uses to decompose a free-text query into issues.
# Ordered by specificity so that e.g. "charged twice" wins over a bare "charge".
ISSUE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("duplicate_charge", ("charged twice", "duplicate charge", "double charge", "charged me twice")),
    ("charge_after_cancellation", ("charged after", "still charged", "canceled but", "cancelled but", "charge after cancellation")),
    ("refund_status", ("refund",)),
    ("incorrect_invoice", ("invoice", "billed the wrong", "wrong amount", "overcharged")),
    ("subscription_status", ("subscription", "plan status", "membership")),
    ("installation_failure", ("install", "update will not install", "won't install", "setup fails")),
    ("password_reset", ("password", "reset link")),
    ("login_failure", ("login", "log in", "sign in", "cannot log", "can't log")),
    ("app_crash", ("crash", "crashes", "freezes", "force close")),
    ("sync_failure", ("sync", "not syncing", "won't sync")),
]


def route_for(issue_type: str) -> str:
    """Return the helper route for an issue, or 'unknown' if unrecognized."""
    return ISSUE_ROUTE.get(issue_type, "unknown")
