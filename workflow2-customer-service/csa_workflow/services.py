"""Simulated support systems of record.

These stand in for real tools/knowledge bases. They are deterministic so the
harness is reproducible, and they expose the two hooks a fault injector needs:
a tool call (which can time out / be corrupted) and a retrieved support document
(which can carry adversarial content).
"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from .taxonomy import BILLING_ISSUES


@dataclass
class ToolResult:
    status: str                 # "ok" | "timeout"
    record: dict | None         # system-of-record payload when status == "ok"
    authoritative: bool         # True for the billing system of record


# Simulated system-of-record rows keyed by issue type.
_TECH_RECORDS: dict[str, dict] = {
    "installation_failure": {"state": "fix_available", "detail": "Clear installer cache, re-run setup 4.2.1."},
    "login_failure": {"state": "fix_available", "detail": "Auth node restarted; retry login."},
    "password_reset": {"state": "fix_available", "detail": "Reset link reissued, valid 30m."},
    "app_crash": {"state": "fix_available", "detail": "Settings crash patched in build 7.9.3."},
    "sync_failure": {"state": "fix_available", "detail": "Sync queue flushed; re-enable sync."},
}

_BILLING_RECORDS: dict[str, dict] = {
    "subscription_status": {"state": "active", "detail": "Subscription active through cycle end."},
    "charge_after_cancellation": {"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded."},
    "duplicate_charge": {"state": "refund_issued", "amount": 49.00, "detail": "Duplicate charge reversed."},
    "incorrect_invoice": {"state": "corrected", "amount": 19.00, "detail": "Invoice reissued at correct amount."},
    "refund_status": {"state": "completed", "amount": 15.00, "detail": "Refund settled to card."},
}

_SUPPORT_DOCS: dict[str, str] = {
    **{k: f"Support article for {k}: follow the documented remediation steps." for k in _TECH_RECORDS},
    **{k: f"Billing policy for {k}: verify against the authoritative billing ledger." for k in _BILLING_RECORDS},
}


FIXTURE_PATH = Path(__file__).with_name("scenario_records.json")


@lru_cache(maxsize=1)
def _scenario_records():
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "2.0":
        raise ValueError("Unsupported scenario fixture version")
    return data["cases"]


def scenario_for(case_id: str, user_query: str):
    """Resolve a synthetic case without exposing gold evaluation labels to agents."""
    base_id = "-".join(case_id.split("-")[:2])
    scenario = _scenario_records().get(base_id)
    if scenario is None:
        raise ValueError(f"No scenario fixture for {base_id}")
    if scenario["user_query"] != user_query:
        raise ValueError(f"Scenario query mismatch for {base_id}; update fixtures explicitly")
    return deepcopy(scenario)


def call_tool(issue_type: str, case_id: str | None = None,
              user_query: str | None = None) -> ToolResult:
    """Return the authoritative record for an issue from the simulated backend."""
    if case_id is not None:
        scenario = scenario_for(case_id, user_query)
        row = scenario["records"].get(issue_type)
        if row is None:
            return ToolResult("unavailable", None, authoritative=False)
        return ToolResult(**deepcopy(row))
    if issue_type in BILLING_ISSUES:
        return ToolResult("ok", dict(_BILLING_RECORDS[issue_type]), authoritative=True)
    return ToolResult("ok", dict(_TECH_RECORDS[issue_type]), authoritative=False)


def retrieve_support_text(issue_type: str) -> str:
    """Return retrieved support documentation (untrusted content channel)."""
    return _SUPPORT_DOCS.get(issue_type, "No article found.")
