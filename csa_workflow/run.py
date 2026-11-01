"""CLI: run the workflow over the dataset and summarize outcomes.

    python -m workflow.run                 # run all cases
    python -m workflow.run --group multi_issue
    python -m workflow.run --fault qa_corruption --verbose
    python -m workflow.run --case BASE-0001-QA_CORRUPTION
"""

from __future__ import annotations

import argparse
from collections import Counter

from .dataset import load_cases
from .orchestrator import run_case


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the support-loop workflow.")
    ap.add_argument("--case")
    ap.add_argument("--group")
    ap.add_argument("--fault")
    ap.add_argument("--path")
    ap.add_argument("--llm", choices=["none", "openai"], default="none",
                    help="model backend for the agents (default: rule-based)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    llm = None
    if args.llm == "openai":
        from .llm import OpenAIClient
        llm = OpenAIClient()

    cases = load_cases(args.path)
    if args.case:
        cases = [c for c in cases if c.case_id == args.case]
    if args.group:
        cases = [c for c in cases if c.scenario_group == args.group]
    if args.fault:
        cases = [c for c in cases if c.fault_type == args.fault]

    match = 0
    by_fault: Counter = Counter()
    by_fault_ok: Counter = Counter()

    for case in cases:
        res = run_case(case, llm=llm)
        ok = res.matches_expected(case)
        match += ok
        by_fault[case.fault_type] += 1
        by_fault_ok[case.fault_type] += ok

        if args.verbose or len(cases) == 1:
            flag = "OK " if ok else "XX "
            print(f"{flag}{case.case_id:32} fault={case.fault_type:17} "
                  f"got={res.final_status:8} exp={case.expected_final_status:8} "
                  f"iters={res.iterations} end={res.terminated_by}")
            if len(cases) == 1:
                for h in res.history:
                    print("   ", h)

    print("\n=== summary ===")
    print(f"expected-status match: {match}/{len(cases)}")
    for ft in sorted(by_fault):
        print(f"  {ft:17} {by_fault_ok[ft]}/{by_fault[ft]}")


if __name__ == "__main__":
    main()
