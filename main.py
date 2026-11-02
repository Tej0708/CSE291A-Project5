from __future__ import annotations

import argparse

from core.config import load_settings
from experiments.run_clean import run_clean_workflow
from experiments.records import experiment_directory
from workflows.registry import list_workflow_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a clean CSE 291A multi-agent workflow."
    )
    parser.add_argument(
        "--workflow",
        choices=list_workflow_names(),
        default="fulfillment",
        help="Workflow to run (default: fulfillment).",
    )
    parser.add_argument(
        "--task-id",
        "--order-id",
        action="append",
        dest="task_ids",
        help=(
            "Task ID to run. Repeat the flag for multiple tasks. "
            "--order-id is kept as a fulfillment-compatible alias. "
            "Default: all tasks for the selected workflow."
        ),
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of repetitions per selected task (default: 1).",
    )
    parser.add_argument("--output-dir", help="New directory for manifest, traces, and results.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    settings = load_settings()
    summaries = run_clean_workflow(
        workflow_name=args.workflow,
        settings=settings,
        task_ids=args.task_ids,
        repetitions=args.runs,
        output_dir=args.output_dir or experiment_directory('clean'),
        progress=True,
    )

    any_failed = False
    for summary in summaries:
        status = "PASS" if summary.passed else "FAIL"
        print(
            f"[{status}] workflow={summary.workflow} task={summary.task_id} "
            f"outcome={summary.outcome} run={summary.run_id}"
        )
        print(
            f"       calls={summary.metrics.model_calls} "
            f"tokens={summary.metrics.total_tokens} "
            f"e2e_latency_ms={summary.metrics.e2e_latency_ms}"
        )
        print(f"       log={summary.log_path}")
        for error in summary.errors:
            print(f"       - {error}")
        any_failed |= not summary.passed

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
