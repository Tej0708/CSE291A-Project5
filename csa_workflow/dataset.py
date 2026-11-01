"""Dataset loader for support_cases.jsonl."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent.parent / "support_cases.jsonl"


@dataclass
class Case:
    case_id: str
    scenario_group: str
    user_query: str
    expected_issues: list[str]
    expected_routing: list[str]
    expected_final_status: str
    max_iterations: int
    expected_invariants: list[str]
    fault_type: str
    fault_config: dict | None
    expected_behavior: str
    split: str
    raw: dict


def load_cases(path: str | Path | None = None) -> list[Case]:
    path = Path(path) if path else _DEFAULT
    cases: list[Case] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            cases.append(Case(
                case_id=d["case_id"],
                scenario_group=d["scenario_group"],
                user_query=d["user_query"],
                expected_issues=d["expected_issues"],
                expected_routing=d["expected_routing"],
                expected_final_status=d["expected_final_status"],
                max_iterations=d["max_iterations"],
                expected_invariants=d["expected_invariants"],
                fault_type=d["fault_type"],
                fault_config=d.get("fault_config"),
                expected_behavior=d["expected_behavior"],
                split=d.get("split", "dev"),
                raw=d,
            ))
    return cases
