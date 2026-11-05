"""Verified analyzer for Workflow 1 live fault/recovery experiments.

Run from the project root:
    python -m experiments.analyze_live_fault_recovery \
        results/fulfillment/eval_live_final_r3

The analyzer is read-only with respect to raw experiment evidence. It writes only
<experiment_dir>/analysis/ and is intentionally stdlib-only.

Primary human-facing output:
    analysis/summary.md

Important semantics used here:
- final correctness = run completed AND task checker passed AND full checker passed.
- eligible comparison = runner-declared paired comparison (passing clean control,
  completed pair, actual fault activation).
- agent exposure != fault validity. Always-verify can correctly stop a corrupted
  artifact before another agent consumes it, and executor-stage faults have no later
  agent by topology.
- "fault exercised" means there is concrete trace evidence of exposure, observed
  corruption, a controlled interruption, dependency impact, or a policy-invalid action.
- tool_calls is kept exactly as the experiment defines it: business/tool activity PLUS
  verification calls. nonverification_tool_calls = tool_calls - verification_calls.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

MODES = ("unprotected", "full_restart", "always_verify")
FAULT_CLASSES = ("accidental", "adversarial")
STOP_ERROR_TYPES = {
    "AuthenticationError", "PermissionDeniedError", "RateLimitError",
    "APIConnectionError", "APITimeoutError", "InternalServerError",
    "InferenceBudgetExceeded", "BudgetExceeded", "BadRequestError",
    "NotFoundError", "UnprocessableEntityError", "FaultConfigurationError",
}

PAIR_DELTA_KEYS = (
    "delta_model_calls",
    "delta_tool_calls",
    "delta_verification_calls",
    "delta_e2e_latency_ms",
    "delta_reported_total_tokens",
)

GENERATED_FILES = {
    "summary.md",
    "analysis.json",
    "by_mode.csv",
    "by_class_and_mode.csv",
    "by_fault.csv",
    "by_mode_and_fault.csv",
    "clean_metrics.csv",
    "clean_overhead.csv",
    "variability.csv",
    "integrity_issues.csv",
    "notable_outcomes.csv",
    "notable_outcomes_summary.csv",
    "review_queue.csv",
    # v1 artifact; remove so stale output cannot be mistaken for current logic.
    "anomalies.csv",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("experiment_dir", type=Path, help="Directory produced by run_live_fault_recovery.py")
    p.add_argument(
        "--output-dir",
        type=Path,
        help="Default: <experiment_dir>/analysis. Only generated analysis files are replaced.",
    )
    return p.parse_args(argv)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL in {path} line {line_number}: {exc}") from exc
    return rows


def parse_scalar(value: str) -> Any:
    if value == "":
        return None
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: parse_scalar(v) for k, v in row.items()} for row in csv.DictReader(f)]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def stats(values: Iterable[Any]) -> dict[str, Any]:
    xs = [float(x) for x in values if is_number(x)]
    if not xs:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "median": statistics.median(xs),
        "stdev": statistics.stdev(xs) if len(xs) >= 2 else 0.0,
        "min": min(xs),
        "max": max(xs),
    }


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{100.0 * value:.1f}%"


def num(value: Any, digits: int = 1) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "N/A"
        return f"{value:.{digits}f}"
    return str(value)



def money(value: Any, digits: int = 6) -> str:
    """Format dollar values without confusing negative zero after rounding."""
    if not is_number(value):
        return "N/A"
    v = float(value)
    threshold = 0.5 * (10 ** -digits)
    if abs(v) < threshold:
        v = 0.0
    return f"${v:.{digits}f}"

def mean_sd(mean: Any, stdev: Any, digits: int = 1) -> str:
    if not is_number(mean):
        return "N/A"
    if not is_number(stdev):
        return num(mean, digits)
    return f"{float(mean):.{digits}f} ± {float(stdev):.{digits}f}"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |")
    return "\n".join(lines) + "\n"


def group_by(rows: Iterable[dict[str, Any]], *keys: str) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    out: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(tuple(row.get(k) for k in keys), []).append(row)
    return out


def metric(row: dict[str, Any], key: str) -> Any:
    metrics = row.get("metrics") or {}
    wasted = row.get("wasted_work") or {}
    if key in metrics:
        return metrics.get(key)
    if key in wasted:
        return wasted.get(key)
    if key == "recovery_latency_ms":
        return row.get("recovery_latency_ms")
    return row.get(key)


def propagation(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("propagation") or {}


def final_correct(row: dict[str, Any]) -> bool:
    return (
        row.get("run_status") == "completed"
        and row.get("task_passed") is True
        and row.get("checker_passed") is True
    )


def agent_exposed(row: dict[str, Any]) -> bool:
    return bool(propagation(row).get("delivered_to_agents"))


def observed_corruption(row: dict[str, Any]) -> bool:
    return bool(propagation(row).get("observed_corrupted_stages"))


def controlled_interruption(row: dict[str, Any]) -> bool:
    return bool(propagation(row).get("controlled_interruption"))


def fault_exercised(row: dict[str, Any]) -> bool:
    """Concrete evidence that the injected fault actually exercised the workflow.

    This deliberately does NOT require downstream-agent exposure. Verification may stop a
    corrupted artifact before another agent receives it, and an executor-stage corruption can
    affect tool actions without any later agent existing.
    """
    if row.get("fault_activated") is not True:
        return False
    p = propagation(row)
    return bool(
        p.get("delivered_to_agents")
        or p.get("dependency_affected_stages")
        or p.get("observed_corrupted_stages")
        or p.get("controlled_interruption")
        or (p.get("unauthorized_attempts") or 0) > 0
        or (p.get("unauthorized_dispatched") or 0) > 0
        or (p.get("unauthorized_executed") or 0) > 0
    )


def trace_paths(row: dict[str, Any]) -> list[str]:
    return [a.get("log_path") for a in row.get("attempts") or [] if a.get("log_path")]


def trial_cost(row: dict[str, Any], spend: dict[str, Any]) -> float | None:
    inp_price = spend.get("input_cost_per_token")
    out_price = spend.get("output_cost_per_token")
    inp = metric(row, "reported_input_tokens")
    out = metric(row, "reported_output_tokens")
    if not all(is_number(x) for x in (inp_price, out_price, inp, out)):
        return None
    return float(inp) * float(inp_price) + float(out) * float(out_price)


def pair_trials(trials: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in trials:
        pid = str(row.get("pair_id"))
        grouped.setdefault(pid, {})[str(row.get("condition"))] = row
    return grouped


def approx_equal(a: Any, b: Any, tol: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if is_number(a) and is_number(b):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    return a == b


def issue(kind: str, severity: str, message: str, **context: Any) -> dict[str, Any]:
    return {"kind": kind, "severity": severity, "message": message, **context}


def validate_sources(
    trials: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, Any]],
    trials_csv_rows: list[dict[str, Any]],
    completion: dict[str, Any],
    spend: dict[str, Any],
    runner_summary: dict[str, Any],
    experiment_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cross-check generated files against trials.jsonl instead of trusting one summary file."""
    issues: list[dict[str, Any]] = []
    pairs = pair_trials(trials)

    slots = [r.get("slot") for r in trials]
    if len(slots) != len(set(slots)):
        issues.append(issue("duplicate_slot", "ERROR", "Duplicate trial slot numbers exist."))
    if slots and all(isinstance(x, int) for x in slots):
        expected = set(range(1, len(slots) + 1))
        if set(slots) != expected:
            issues.append(issue("slot_gap", "ERROR", "Trial slots are not exactly 1..N."))

    planned = completion.get("planned_slots")
    attempted = completion.get("attempted_slots")

    # plan.jsonl is the predeclared schedule. Its row count/order should match the run.
    if plan_rows:
        if planned is not None and len(plan_rows) != planned:
            issues.append(issue("plan_count_mismatch", "ERROR", f"plan.jsonl has {len(plan_rows)} rows but completion planned_slots={planned}."))
        plan_keys = ("pair_id", "repetition", "case_id", "fault_id", "fault_type", "fault_class", "stage", "surface", "mode", "condition")
        plan_mismatches = 0
        for index, trial_row in enumerate(trials):
            if index >= len(plan_rows):
                plan_mismatches += 1
                continue
            plan_row = plan_rows[index]
            if any(trial_row.get(k) != plan_row.get(k) for k in plan_keys):
                plan_mismatches += 1
        if plan_mismatches:
            issues.append(issue("plan_trial_mismatch", "ERROR", f"{plan_mismatches} attempted trial row(s) do not match the predeclared plan at the same slot."))

    # trials.csv is a flattened convenience copy. Verify core columns against JSONL.
    if trials_csv_rows:
        if len(trials_csv_rows) != len(trials):
            issues.append(issue("trials_csv_count_mismatch", "ERROR", f"trials.csv has {len(trials_csv_rows)} rows but trials.jsonl has {len(trials)}."))
        csv_mismatches = 0
        csv_by_slot = {r.get("slot"): r for r in trials_csv_rows}
        for r in trials:
            c = csv_by_slot.get(r.get("slot"))
            if c is None:
                csv_mismatches += 1
                continue
            expected = {
                "pair_id": r.get("pair_id"), "repetition": r.get("repetition"),
                "case_id": r.get("case_id"), "fault_id": r.get("fault_id"),
                "mode": r.get("mode"), "condition": r.get("condition"),
                "run_status": r.get("run_status"), "checker_passed": r.get("checker_passed"),
                "task_passed": r.get("task_passed"), "fault_activated": r.get("fault_activated"),
                "model_calls": metric(r, "model_calls"), "tool_calls": metric(r, "tool_calls"),
                "verification_calls": metric(r, "verification_calls"),
                "reported_total_tokens": metric(r, "reported_total_tokens"),
                "e2e_latency_ms": metric(r, "e2e_latency_ms"),
            }
            if any(not approx_equal(c.get(k), v) for k, v in expected.items()):
                csv_mismatches += 1
        if csv_mismatches:
            issues.append(issue("trials_csv_value_mismatch", "ERROR", f"{csv_mismatches} trials.csv row(s) disagree with trials.jsonl core fields."))

    if attempted is not None and attempted != len(trials):
        issues.append(issue("completion_mismatch", "ERROR", f"completion.json attempted={attempted}, trials.jsonl rows={len(trials)}."))
    if planned is not None and completion.get("not_attempted_slots") != planned - len(trials):
        issues.append(issue("completion_mismatch", "ERROR", "completion.json not_attempted_slots does not match planned - actual rows."))

    duplicate_conditions = []
    missing_conditions = []
    for pid, conds in pairs.items():
        # dict overwrites duplicates, so inspect raw count too.
        raw = [r for r in trials if str(r.get("pair_id")) == pid]
        cond_counts = {c: sum(r.get("condition") == c for r in raw) for c in ("clean", "fault")}
        if any(v > 1 for v in cond_counts.values()):
            duplicate_conditions.append(pid)
        if set(conds) != {"clean", "fault"}:
            missing_conditions.append(pid)
    if duplicate_conditions:
        issues.append(issue("duplicate_pair_condition", "ERROR", f"{len(duplicate_conditions)} pair(s) contain duplicate clean/fault conditions."))
    if missing_conditions:
        issues.append(issue("incomplete_pair", "ERROR", f"{len(missing_conditions)} pair(s) are missing clean or fault condition."))

    official = {str(p.get("pair_id")): p for p in pair_rows}
    if set(official) != set(pairs):
        issues.append(issue(
            "paired_csv_pair_set_mismatch", "ERROR",
            f"paired.csv has {len(official)} IDs while trials.jsonl yields {len(pairs)}; ID sets differ.",
        ))

    delta_fields = {
        "delta_model_calls": "model_calls",
        "delta_tool_calls": "tool_calls",
        "delta_verification_calls": "verification_calls",
        "delta_e2e_latency_ms": "e2e_latency_ms",
        "delta_reported_total_tokens": "reported_total_tokens",
    }
    mismatches = 0
    for pid in sorted(set(official) & set(pairs)):
        p = official[pid]
        conds = pairs[pid]
        if "clean" not in conds or "fault" not in conds:
            continue
        clean, fault = conds["clean"], conds["fault"]
        expected_complete = bool(
            clean and fault
            and clean.get("experiment_error") is None
            and fault.get("experiment_error") is None
            and clean.get("error_type") not in STOP_ERROR_TYPES
            and fault.get("error_type") not in STOP_ERROR_TYPES
        )
        expected_clean_pass = final_correct(clean)
        expected_activated = fault.get("fault_activated") is True
        expected_eligible = expected_complete and expected_clean_pass and expected_activated
        checks = {
            "complete": expected_complete,
            "clean_pass": expected_clean_pass,
            "activated": expected_activated,
            "eligible_fault_comparison": expected_eligible,
        }
        for k, expected_value in checks.items():
            if p.get(k) != expected_value:
                mismatches += 1
        for delta_key, metric_key in delta_fields.items():
            a, b = metric(clean, metric_key), metric(fault, metric_key)
            expected_delta = float(b) - float(a) if is_number(a) and is_number(b) else None
            if not approx_equal(p.get(delta_key), expected_delta):
                mismatches += 1
    if mismatches:
        issues.append(issue("paired_csv_value_mismatch", "ERROR", f"Found {mismatches} paired.csv field mismatch(es) against trials.jsonl."))

    sum_model_calls = sum((metric(r, "model_calls") or 0) for r in trials)
    sum_input = sum((metric(r, "reported_input_tokens") or 0) for r in trials)
    sum_output = sum((metric(r, "reported_output_tokens") or 0) for r in trials)
    if is_number(spend.get("api_calls_sent")) and spend.get("api_calls_sent") != sum_model_calls:
        issues.append(issue("spend_call_mismatch", "ERROR", f"spend.json api_calls_sent={spend.get('api_calls_sent')} but trials sum to {sum_model_calls}."))
    if is_number(spend.get("provider_input_tokens")) and spend.get("provider_input_tokens") != sum_input:
        issues.append(issue("spend_input_token_mismatch", "ERROR", f"spend input tokens={spend.get('provider_input_tokens')} but trials sum to {sum_input}."))
    if is_number(spend.get("provider_output_tokens")) and spend.get("provider_output_tokens") != sum_output:
        issues.append(issue("spend_output_token_mismatch", "ERROR", f"spend output tokens={spend.get('provider_output_tokens')} but trials sum to {sum_output}."))
    if is_number(spend.get("input_cost_per_token")) and is_number(spend.get("output_cost_per_token")):
        expected_cost = sum_input * float(spend["input_cost_per_token"]) + sum_output * float(spend["output_cost_per_token"])
        if is_number(spend.get("estimated_cost_from_reported_usage_usd")) and not approx_equal(
            expected_cost, spend.get("estimated_cost_from_reported_usage_usd"), tol=1e-10
        ):
            issues.append(issue("spend_cost_mismatch", "ERROR", f"Token-derived cost {expected_cost} disagrees with spend.json estimate {spend.get('estimated_cost_from_reported_usage_usd')}."))

    # Trace accounting: one raw JSONL per workflow attempt.
    expected_attempts = sum((r.get("attempt_count") or 0) for r in trials)
    trace_dir = experiment_dir / "traces"
    actual_traces = len(list(trace_dir.rglob("*.jsonl"))) if trace_dir.exists() else 0
    if actual_traces != expected_attempts:
        issues.append(issue("trace_count_mismatch", "ERROR", f"Raw trace files={actual_traces}, but trial attempt_count sums to {expected_attempts}."))

    # Runner summary cross-checks for the fields that are unambiguous from raw rows.
    expected_summary = {
        "attempted_slots": len(trials),
        "completed_workflows": sum(r.get("run_status") == "completed" for r in trials),
        "activated_fault_runs": sum(r.get("condition") == "fault" and r.get("fault_activated") is True for r in trials),
        "pair_count_attempted": len(pairs),
    }
    for key, expected_value in expected_summary.items():
        if runner_summary and runner_summary.get(key) != expected_value:
            issues.append(issue("runner_summary_mismatch", "ERROR", f"summary.json {key}={runner_summary.get(key)} but raw rows imply {expected_value}."))

    integrity = {
        "trial_rows": len(trials),
        "pair_rows": len(pair_rows),
        "unique_pairs": len(pairs),
        "clean_rows": sum(r.get("condition") == "clean" for r in trials),
        "fault_rows": sum(r.get("condition") == "fault" for r in trials),
        "clean_final_correct": sum(r.get("condition") == "clean" and final_correct(r) for r in trials),
        "faults_activated": sum(r.get("condition") == "fault" and r.get("fault_activated") is True for r in trials),
        "faults_exercised": sum(r.get("condition") == "fault" and fault_exercised(r) for r in trials),
        "summed_model_calls": sum_model_calls,
        "summed_input_tokens": sum_input,
        "summed_output_tokens": sum_output,
        "summed_reported_total_tokens": sum((metric(r, "reported_total_tokens") or 0) for r in trials),
        "summed_attempt_count": sum((r.get("attempt_count") or 0) for r in trials),
        "raw_trace_files": len(list((experiment_dir / "traces").rglob("*.jsonl"))) if (experiment_dir / "traces").exists() else 0,
        "unknown_usage_calls": sum((metric(r, "unknown_usage_calls") or 0) for r in trials),
        "incomplete_model_calls": sum((metric(r, "incomplete_model_calls") or 0) for r in trials),
        "incomplete_tool_calls": sum((metric(r, "incomplete_tool_calls") or 0) for r in trials),
        "incomplete_verification_calls": sum((metric(r, "incomplete_verification_calls") or 0) for r in trials),
        "source_crosscheck_errors": len([x for x in issues if x.get("severity") == "ERROR"]),
    }
    return issues, integrity


def eligible_pair_rows(pair_rows: list[dict[str, Any]], mode: str | None = None, fault_class: str | None = None) -> list[dict[str, Any]]:
    rows = [p for p in pair_rows if p.get("eligible_fault_comparison") is True]
    if mode is not None:
        rows = [p for p in rows if p.get("mode") == mode]
    if fault_class is not None:
        rows = [p for p in rows if p.get("fault_class") == fault_class]
    return rows


def final_success_for_pair(pid: str, pair_map: dict[str, dict[str, dict[str, Any]]]) -> bool:
    pair = pair_map.get(pid) or {}
    return final_correct(pair.get("fault") or {})


def analyze_by_mode(
    trials: list[dict[str, Any]], pair_rows: list[dict[str, Any]], spend: dict[str, Any]
) -> list[dict[str, Any]]:
    pair_map = pair_trials(trials)
    result: list[dict[str, Any]] = []
    for mode in MODES:
        clean = [r for r in trials if r.get("mode") == mode and r.get("condition") == "clean"]
        fault = [r for r in trials if r.get("mode") == mode and r.get("condition") == "fault"]
        eligible = eligible_pair_rows(pair_rows, mode=mode)
        eligible_ids = {str(p.get("pair_id")) for p in eligible}
        eligible_fault_trials = [r for r in fault if str(r.get("pair_id")) in eligible_ids]
        success = [p for p in eligible if final_success_for_pair(str(p.get("pair_id")), pair_map)]
        activated = [r for r in fault if r.get("fault_activated") is True]

        row: dict[str, Any] = {
            "mode": mode,
            "clean_runs": len(clean),
            "clean_final_correct_rate": rate(sum(final_correct(r) for r in clean), len(clean)),
            "fault_runs": len(fault),
            "fault_activation_rate": rate(len(activated), len(fault)),
            "fault_exercised_rate": rate(sum(fault_exercised(r) for r in activated), len(activated)),
            "agent_exposure_rate": rate(sum(agent_exposed(r) for r in activated), len(activated)),
            "observed_corruption_rate": rate(sum(observed_corruption(r) for r in activated), len(activated)),
            "downstream_corruption_rate": rate(sum(bool(propagation(r).get("downstream_corrupted_stages")) for r in activated), len(activated)),
            "controlled_interruption_rate": rate(sum(controlled_interruption(r) for r in activated), len(activated)),
            "eligible_pairs": len(eligible),
            "final_correct_count": len(success),
            "final_correct_rate": rate(len(success), len(eligible)),
            "policy_invalid_attempts": sum((propagation(r).get("unauthorized_attempts") or 0) for r in eligible_fault_trials),
            "policy_invalid_dispatched": sum((propagation(r).get("unauthorized_dispatched") or 0) for r in eligible_fault_trials),
            "policy_invalid_executed": sum((propagation(r).get("unauthorized_executed") or 0) for r in eligible_fault_trials),
            "mean_dependency_affected_stages": stats(len(propagation(r).get("dependency_affected_stages") or []) for r in eligible_fault_trials)["mean"],
            "mean_observed_corrupted_stages": stats(len(propagation(r).get("observed_corrupted_stages") or []) for r in eligible_fault_trials)["mean"],
        }

        for key in (
            "model_calls", "tool_calls", "verification_calls", "reported_total_tokens",
            "e2e_latency_ms", "recovery_latency_ms", "discarded_model_calls", "recomputed_model_calls",
            "recomputed_stages", "reported_discarded_tokens",
        ):
            s = stats(metric(r, key) for r in eligible_fault_trials)
            row[f"fault_{key}_mean"] = s["mean"]
            row[f"fault_{key}_median"] = s["median"]
            row[f"fault_{key}_stdev"] = s["stdev"]

        for key in PAIR_DELTA_KEYS:
            s = stats(p.get(key) for p in eligible)
            row[f"{key}_mean"] = s["mean"]
            row[f"{key}_median"] = s["median"]
            row[f"{key}_stdev"] = s["stdev"]

        nonverification_deltas = [
            float(p["delta_tool_calls"]) - float(p["delta_verification_calls"])
            for p in eligible
            if is_number(p.get("delta_tool_calls")) and is_number(p.get("delta_verification_calls"))
        ]
        ss = stats(nonverification_deltas)
        row["delta_nonverification_tool_calls_mean"] = ss["mean"]
        row["delta_nonverification_tool_calls_median"] = ss["median"]
        row["delta_nonverification_tool_calls_stdev"] = ss["stdev"]

        cost_deltas = []
        for pair_row in eligible:
            pair = pair_map.get(str(pair_row.get("pair_id"))) or {}
            clean_r, fault_r = pair.get("clean"), pair.get("fault")
            if clean_r and fault_r:
                a, b = trial_cost(clean_r, spend), trial_cost(fault_r, spend)
                if is_number(a) and is_number(b):
                    cost_deltas.append(float(b) - float(a))
        ss = stats(cost_deltas)
        row["delta_estimated_cost_usd_mean"] = ss["mean"]
        row["delta_estimated_cost_usd_median"] = ss["median"]
        row["delta_estimated_cost_usd_stdev"] = ss["stdev"]
        result.append(row)
    return result

def analyze_by_class_and_mode(
    trials: list[dict[str, Any]], pair_rows: list[dict[str, Any]], spend: dict[str, Any]
) -> list[dict[str, Any]]:
    """Primary class-separated aggregates required by the project instructions."""
    pair_map = pair_trials(trials)
    rows: list[dict[str, Any]] = []
    for fault_class in FAULT_CLASSES:
        for mode in MODES:
            eligible = eligible_pair_rows(pair_rows, mode=mode, fault_class=fault_class)
            eligible_ids = {str(p.get("pair_id")) for p in eligible}
            fault_trials = [
                r for r in trials
                if r.get("condition") == "fault"
                and r.get("mode") == mode
                and r.get("fault_class") == fault_class
                and str(r.get("pair_id")) in eligible_ids
            ]
            successes = sum(final_success_for_pair(str(p.get("pair_id")), pair_map) for p in eligible)
            out: dict[str, Any] = {
                "fault_class": fault_class,
                "mode": mode,
                "eligible_pairs": len(eligible),
                "final_correct_count": successes,
                "final_correct_rate": rate(successes, len(eligible)),
                "fault_activation_rate": rate(sum(r.get("fault_activated") is True for r in fault_trials), len(fault_trials)),
                "fault_exercised_rate": rate(sum(fault_exercised(r) for r in fault_trials), len(fault_trials)),
                "agent_exposure_rate": rate(sum(agent_exposed(r) for r in fault_trials), len(fault_trials)),
                "observed_corruption_rate": rate(sum(observed_corruption(r) for r in fault_trials), len(fault_trials)),
                "downstream_corruption_rate": rate(sum(bool(propagation(r).get("downstream_corrupted_stages")) for r in fault_trials), len(fault_trials)),
                "controlled_interruption_rate": rate(sum(controlled_interruption(r) for r in fault_trials), len(fault_trials)),
                "policy_invalid_attempts": sum((propagation(r).get("unauthorized_attempts") or 0) for r in fault_trials),
                "policy_invalid_executed": sum((propagation(r).get("unauthorized_executed") or 0) for r in fault_trials),
                "mean_dependency_affected_stages": stats(len(propagation(r).get("dependency_affected_stages") or []) for r in fault_trials)["mean"],
                "mean_observed_corrupted_stages": stats(len(propagation(r).get("observed_corrupted_stages") or []) for r in fault_trials)["mean"],
            }
            for key in PAIR_DELTA_KEYS:
                ss = stats(p.get(key) for p in eligible)
                out[f"{key}_mean"] = ss["mean"]
                out[f"{key}_median"] = ss["median"]
                out[f"{key}_stdev"] = ss["stdev"]
            nonverification = [
                float(p["delta_tool_calls"]) - float(p["delta_verification_calls"])
                for p in eligible
                if is_number(p.get("delta_tool_calls")) and is_number(p.get("delta_verification_calls"))
            ]
            ss = stats(nonverification)
            out["delta_nonverification_tool_calls_mean"] = ss["mean"]
            out["delta_nonverification_tool_calls_stdev"] = ss["stdev"]
            for key in ("recomputed_stages", "recomputed_model_calls", "discarded_model_calls", "reported_discarded_tokens", "recovery_latency_ms"):
                ss = stats(metric(r, key) for r in fault_trials)
                out[f"{key}_mean"] = ss["mean"]
                out[f"{key}_stdev"] = ss["stdev"]
            positive_recovery = [float(metric(r, "recovery_latency_ms")) for r in fault_trials
                                 if is_number(metric(r, "recovery_latency_ms")) and float(metric(r, "recovery_latency_ms")) > 0]
            recovery_ss = stats(positive_recovery)
            out["recovery_work_runs"] = recovery_ss["n"]
            out["recovery_latency_when_positive_mean"] = recovery_ss["mean"]
            out["recovery_latency_when_positive_stdev"] = recovery_ss["stdev"]
            cost_deltas = []
            for p_row in eligible:
                pair = pair_map.get(str(p_row.get("pair_id"))) or {}
                if pair.get("clean") and pair.get("fault"):
                    a, b = trial_cost(pair["clean"], spend), trial_cost(pair["fault"], spend)
                    if is_number(a) and is_number(b):
                        cost_deltas.append(float(b) - float(a))
            ss = stats(cost_deltas)
            out["delta_estimated_cost_usd_mean"] = ss["mean"]
            out["delta_estimated_cost_usd_stdev"] = ss["stdev"]
            rows.append(out)
    return rows

def analyze_by_mode_and_fault(
    trials: list[dict[str, Any]], pair_rows: list[dict[str, Any]], spend: dict[str, Any]
) -> list[dict[str, Any]]:
    pair_map = pair_trials(trials)
    meta: dict[str, dict[str, Any]] = {}
    for r in trials:
        if r.get("fault_id"):
            meta.setdefault(str(r["fault_id"]), r)
    result: list[dict[str, Any]] = []
    grouped = group_by(pair_rows, "fault_id", "mode")
    for (fault_id, mode), ps in sorted(grouped.items()):
        eligible = [p for p in ps if p.get("eligible_fault_comparison") is True]
        success_count = sum(final_success_for_pair(str(p.get("pair_id")), pair_map) for p in eligible)
        eligible_ids = {str(p.get("pair_id")) for p in eligible}
        fault_trials = [
            r for r in trials
            if r.get("fault_id") == fault_id and r.get("mode") == mode
            and r.get("condition") == "fault" and str(r.get("pair_id")) in eligible_ids
        ]
        m = meta.get(str(fault_id), {})
        row: dict[str, Any] = {
            "fault_id": fault_id,
            "case_id": m.get("case_id"),
            "fault_type": m.get("fault_type"),
            "fault_class": m.get("fault_class"),
            "stage": m.get("stage"),
            "surface": m.get("surface"),
            "mode": mode,
            "repetitions_attempted": len(ps),
            "eligible_pairs": len(eligible),
            "final_correct_count": success_count,
            "final_correct_rate": rate(success_count, len(eligible)),
            "activation_rate": rate(sum(r.get("fault_activated") is True for r in fault_trials), len(fault_trials)),
            "fault_exercised_rate": rate(sum(fault_exercised(r) for r in fault_trials), len(fault_trials)),
            "agent_exposure_rate": rate(sum(agent_exposed(r) for r in fault_trials), len(fault_trials)),
            "observed_corruption_rate": rate(sum(observed_corruption(r) for r in fault_trials), len(fault_trials)),
            "downstream_corruption_rate": rate(sum(bool(propagation(r).get("downstream_corrupted_stages")) for r in fault_trials), len(fault_trials)),
            "controlled_interruption_rate": rate(sum(controlled_interruption(r) for r in fault_trials), len(fault_trials)),
            "policy_invalid_attempts": sum((propagation(r).get("unauthorized_attempts") or 0) for r in fault_trials),
            "policy_invalid_executed": sum((propagation(r).get("unauthorized_executed") or 0) for r in fault_trials),
        }
        for key in PAIR_DELTA_KEYS:
            s = stats(p.get(key) for p in eligible)
            row[f"{key}_mean"] = s["mean"]
            row[f"{key}_median"] = s["median"]
            row[f"{key}_stdev"] = s["stdev"]
        nonverification = [
            float(p["delta_tool_calls"]) - float(p["delta_verification_calls"])
            for p in eligible
            if is_number(p.get("delta_tool_calls")) and is_number(p.get("delta_verification_calls"))
        ]
        s = stats(nonverification)
        row["delta_nonverification_tool_calls_mean"] = s["mean"]
        row["delta_nonverification_tool_calls_stdev"] = s["stdev"]
        for key in ("recomputed_stages", "recomputed_model_calls", "discarded_model_calls", "reported_discarded_tokens", "recovery_latency_ms"):
            s = stats(metric(r, key) for r in fault_trials)
            row[f"{key}_mean"] = s["mean"]
            row[f"{key}_stdev"] = s["stdev"]

        cost_deltas = []
        for p in eligible:
            pair = pair_map.get(str(p.get("pair_id"))) or {}
            if pair.get("clean") and pair.get("fault"):
                a, b = trial_cost(pair["clean"], spend), trial_cost(pair["fault"], spend)
                if is_number(a) and is_number(b):
                    cost_deltas.append(float(b) - float(a))
        s = stats(cost_deltas)
        row["delta_estimated_cost_usd_mean"] = s["mean"]
        row["delta_estimated_cost_usd_stdev"] = s["stdev"]
        result.append(row)
    return result


def analyze_by_fault(by_mode_fault: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for (fault_id,), rows in sorted(group_by(by_mode_fault, "fault_id").items()):
        first = rows[0]
        out: dict[str, Any] = {
            "fault_id": fault_id,
            "case_id": first.get("case_id"),
            "fault_type": first.get("fault_type"),
            "fault_class": first.get("fault_class"),
            "stage": first.get("stage"),
            "surface": first.get("surface"),
        }
        for mode in MODES:
            r = next((x for x in rows if x.get("mode") == mode), None)
            out[f"{mode}_eligible_n"] = r.get("eligible_pairs") if r else 0
            out[f"{mode}_final_correct_rate"] = r.get("final_correct_rate") if r else None
            out[f"{mode}_delta_model_calls_mean"] = r.get("delta_model_calls_mean") if r else None
            out[f"{mode}_delta_tokens_mean"] = r.get("delta_reported_total_tokens_mean") if r else None
            out[f"{mode}_delta_latency_ms_mean"] = r.get("delta_e2e_latency_ms_mean") if r else None
            out[f"{mode}_policy_invalid_executed"] = r.get("policy_invalid_executed") if r else None
        result.append(out)
    return result


def analyze_clean_metrics(trials: list[dict[str, Any]], spend: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        clean = [r for r in trials if r.get("condition") == "clean" and r.get("mode") == mode]
        row: dict[str, Any] = {
            "mode": mode,
            "n": len(clean),
            "final_correct_rate": rate(sum(final_correct(r) for r in clean), len(clean)),
        }
        derived: dict[str, list[Any]] = {
            "model_calls": [metric(r, "model_calls") for r in clean],
            "tool_calls": [metric(r, "tool_calls") for r in clean],
            "verification_calls": [metric(r, "verification_calls") for r in clean],
            "nonverification_tool_calls": [
                float(metric(r, "tool_calls")) - float(metric(r, "verification_calls"))
                if is_number(metric(r, "tool_calls")) and is_number(metric(r, "verification_calls")) else None
                for r in clean
            ],
            "reported_total_tokens": [metric(r, "reported_total_tokens") for r in clean],
            "e2e_latency_ms": [metric(r, "e2e_latency_ms") for r in clean],
            "verification_latency_ms": [metric(r, "verification_latency_ms") for r in clean],
            "estimated_cost_usd": [trial_cost(r, spend) for r in clean],
        }
        for key, values in derived.items():
            s = stats(values)
            row[f"{key}_mean"] = s["mean"]
            row[f"{key}_median"] = s["median"]
            row[f"{key}_stdev"] = s["stdev"]
        rows.append(row)
    return rows


def analyze_clean_overhead(trials: list[dict[str, Any]], spend: dict[str, Any]) -> list[dict[str, Any]]:
    """Matched clean-mode differences versus unprotected for same fault target + repetition.

    Model output token counts and end-to-end latency are stochastic observations, so small
    negative differences are valid and should NOT be interpreted as negative structural cost.
    """
    clean = [r for r in trials if r.get("condition") == "clean"]
    grouped = group_by(clean, "repetition", "fault_id")
    result: list[dict[str, Any]] = []
    for mode in ("full_restart", "always_verify"):
        values: dict[str, list[float]] = {
            "model_calls": [],
            "tool_calls": [],
            "verification_calls": [],
            "nonverification_tool_calls": [],
            "reported_total_tokens": [],
            "e2e_latency_ms": [],
            "estimated_cost_usd": [],
        }
        matched = 0
        for _, group in grouped.items():
            base = next((r for r in group if r.get("mode") == "unprotected"), None)
            other = next((r for r in group if r.get("mode") == mode), None)
            if not base or not other or not final_correct(base) or not final_correct(other):
                continue
            matched += 1
            for key in ("model_calls", "tool_calls", "verification_calls", "reported_total_tokens", "e2e_latency_ms"):
                a, b = metric(base, key), metric(other, key)
                if is_number(a) and is_number(b):
                    values[key].append(float(b) - float(a))
            a_non = (
                float(metric(base, "tool_calls")) - float(metric(base, "verification_calls"))
                if is_number(metric(base, "tool_calls")) and is_number(metric(base, "verification_calls")) else None
            )
            b_non = (
                float(metric(other, "tool_calls")) - float(metric(other, "verification_calls"))
                if is_number(metric(other, "tool_calls")) and is_number(metric(other, "verification_calls")) else None
            )
            if is_number(a_non) and is_number(b_non):
                values["nonverification_tool_calls"].append(float(b_non) - float(a_non))
            a_cost, b_cost = trial_cost(base, spend), trial_cost(other, spend)
            if is_number(a_cost) and is_number(b_cost):
                values["estimated_cost_usd"].append(float(b_cost) - float(a_cost))

        row: dict[str, Any] = {"mode": mode, "matched_clean_controls": matched}
        for key, vals in values.items():
            s = stats(vals)
            row[f"delta_{key}_mean"] = s["mean"]
            row[f"delta_{key}_median"] = s["median"]
            row[f"delta_{key}_stdev"] = s["stdev"]
        result.append(row)
    return result


def analyze_variability(by_mode_fault: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in by_mode_fault:
        rows.append({
            "fault_id": r.get("fault_id"),
            "fault_class": r.get("fault_class"),
            "mode": r.get("mode"),
            "eligible_pairs": r.get("eligible_pairs"),
            "final_correct_rate": r.get("final_correct_rate"),
            "delta_model_calls_mean": r.get("delta_model_calls_mean"),
            "delta_model_calls_stdev": r.get("delta_model_calls_stdev"),
            "delta_tokens_mean": r.get("delta_reported_total_tokens_mean"),
            "delta_tokens_stdev": r.get("delta_reported_total_tokens_stdev"),
            "delta_latency_ms_mean": r.get("delta_e2e_latency_ms_mean"),
            "delta_latency_ms_stdev": r.get("delta_e2e_latency_ms_stdev"),
            "recovery_latency_ms_mean": r.get("recovery_latency_ms_mean"),
            "recovery_latency_ms_stdev": r.get("recovery_latency_ms_stdev"),
            "recomputed_stages_mean": r.get("recomputed_stages_mean"),
            "recomputed_stages_stdev": r.get("recomputed_stages_stdev"),
            "recomputed_model_calls_mean": r.get("recomputed_model_calls_mean"),
            "recomputed_model_calls_stdev": r.get("recomputed_model_calls_stdev"),
            "discarded_model_calls_mean": r.get("discarded_model_calls_mean"),
            "discarded_model_calls_stdev": r.get("discarded_model_calls_stdev"),
        })
    return rows


def review_row(row: dict[str, Any], kind: str, severity: str, category: str, reason: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "category": category,
        "slot": row.get("slot"),
        "pair_id": row.get("pair_id"),
        "repetition": row.get("repetition"),
        "case_id": row.get("case_id"),
        "fault_id": row.get("fault_id"),
        "fault_class": row.get("fault_class"),
        "mode": row.get("mode"),
        "condition": row.get("condition"),
        "reason": reason,
        "trace_paths": ";".join(trace_paths(row)),
    }


def build_review_queue(
    trials: list[dict[str, Any]], pair_rows: list[dict[str, Any]], source_issues: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    integrity: list[dict[str, Any]] = []
    notable: list[dict[str, Any]] = []
    pair_map = {str(p.get("pair_id")): p for p in pair_rows}

    # Dataset/file-level source cross-check issues.
    for src in source_issues:
        integrity.append({
            "kind": "INTEGRITY",
            "severity": src.get("severity", "ERROR"),
            "category": src.get("kind"),
            "slot": None,
            "pair_id": None,
            "repetition": None,
            "case_id": None,
            "fault_id": None,
            "fault_class": None,
            "mode": None,
            "condition": None,
            "reason": src.get("message"),
            "trace_paths": "",
        })

    for r in trials:
        condition = r.get("condition")
        mode = r.get("mode")
        metrics = r.get("metrics") or {}
        p = propagation(r)

        if r.get("experiment_error"):
            integrity.append(review_row(r, "INTEGRITY", "ERROR", "experiment_error", str(r.get("experiment_error"))))
        if condition == "clean" and not final_correct(r):
            integrity.append(review_row(r, "INTEGRITY", "ERROR", "clean_control_failed", "Clean control was not fully correct."))
        if condition == "fault" and r.get("fault_activated") is not True:
            integrity.append(review_row(r, "INTEGRITY", "ERROR", "fault_not_activated", "Scheduled fault did not activate; do not count as recovery evidence."))
        if condition == "fault" and r.get("fault_activated") is True and not fault_exercised(r):
            integrity.append(review_row(r, "INTEGRITY", "ERROR", "fault_not_exercised", "Fault activated but no trace evidence shows exposure, corruption, interruption, dependency impact, or policy-invalid action."))
        if (metrics.get("unknown_usage_calls") or 0) > 0:
            integrity.append(review_row(r, "INTEGRITY", "WARN", "unknown_token_usage", f"{metrics.get('unknown_usage_calls')} model call(s) have incomplete token usage."))
        incomplete = sum((metrics.get(k) or 0) for k in (
            "incomplete_model_calls", "incomplete_tool_calls", "incomplete_verification_calls"
        ))
        if incomplete > 0:
            integrity.append(review_row(r, "INTEGRITY", "WARN", "incomplete_calls", f"Trace contains {incomplete} incomplete call(s)."))

        official_pair = pair_map.get(str(r.get("pair_id")))
        eligible = bool(official_pair and official_pair.get("eligible_fault_comparison") is True)
        if condition == "fault" and eligible:
            if mode in ("full_restart", "always_verify") and not final_correct(r):
                notable.append(review_row(r, "OUTCOME", "REVIEW", "recovery_failed", f"{mode} did not recover final correctness."))
            if mode == "unprotected" and final_correct(r):
                if observed_corruption(r):
                    reason = "Unprotected run was final-correct despite observed corrupted stage(s)."
                    category = "unprotected_final_correct_with_observed_corruption"
                else:
                    reason = "Unprotected run was final-correct after an activated fault; no corrupted stage was observed."
                    category = "unprotected_final_correct_no_observed_corruption"
                notable.append(review_row(r, "OUTCOME", "NOTE", category, reason))

            if (p.get("unauthorized_executed") or 0) > 0:
                notable.append(review_row(
                    r, "OUTCOME", "REVIEW", "policy_invalid_action_executed",
                    f"{p.get('unauthorized_executed')} policy-invalid action(s) changed simulated state before recovery/finalization.",
                ))

    # Outcome consistency across repetitions.
    fault_trials = [r for r in trials if r.get("condition") == "fault"]
    for (fault_id, mode), rows in group_by(fault_trials, "fault_id", "mode").items():
        eligible_rows = [
            r for r in rows
            if (pair_map.get(str(r.get("pair_id"))) or {}).get("eligible_fault_comparison") is True
        ]
        outcomes = {final_correct(r) for r in eligible_rows}
        if len(eligible_rows) >= 2 and len(outcomes) > 1:
            notable.append(review_row(
                eligible_rows[0], "OUTCOME", "REVIEW", "outcome_varied_across_repetitions",
                f"{fault_id}/{mode} had different final-correctness outcomes across {len(eligible_rows)} eligible repetitions.",
            ))

    # High-latency observation only; provider latency variability is not an integrity failure.
    for (mode, condition), rows in group_by(trials, "mode", "condition").items():
        vals = [metric(r, "e2e_latency_ms") for r in rows if is_number(metric(r, "e2e_latency_ms"))]
        if len(vals) < 5:
            continue
        med = statistics.median(vals)
        if med <= 0:
            continue
        for r in rows:
            value = metric(r, "e2e_latency_ms")
            if is_number(value) and float(value) > 3.0 * med:
                notable.append(review_row(
                    r, "OUTCOME", "NOTE", "latency_outlier",
                    f"E2E latency {float(value):.1f} ms is >3× the {mode}/{condition} median ({med:.1f} ms).",
                ))

    severity_order = {"ERROR": 0, "WARN": 1, "REVIEW": 2, "NOTE": 3}
    integrity.sort(key=lambda x: (severity_order.get(str(x.get("severity")), 9), x.get("slot") or 10**9, str(x.get("category"))))
    notable.sort(key=lambda x: (severity_order.get(str(x.get("severity")), 9), x.get("slot") or 10**9, str(x.get("category"))))
    review = integrity + notable
    return integrity, notable, review


def summarize_notable_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated per-trial flags into report-friendly fault/mode groups."""
    result: list[dict[str, Any]] = []
    grouped = group_by(rows, "severity", "category", "fault_id", "mode")
    for (severity, category, fault_id, mode), items in sorted(grouped.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][2]), str(kv[0][3]), str(kv[0][1]))):
        reps = sorted({x.get("repetition") for x in items if x.get("repetition") is not None})
        reason = items[0].get("reason") if items else None
        result.append({
            "severity": severity,
            "category": category,
            "fault_id": fault_id,
            "mode": mode,
            "count": len(items),
            "repetitions": ",".join(str(x) for x in reps),
            "representative_reason": reason,
            "representative_trace_paths": items[0].get("trace_paths") if items else "",
        })
    return result


def build_markdown(
    experiment_dir: Path,
    completion: dict[str, Any],
    spend: dict[str, Any],
    integrity_summary: dict[str, Any],
    source_issues: list[dict[str, Any]],
    by_mode: list[dict[str, Any]],
    by_class_mode: list[dict[str, Any]],
    by_fault: list[dict[str, Any]],
    clean_metrics: list[dict[str, Any]],
    clean_overhead: list[dict[str, Any]],
    variability: list[dict[str, Any]],
    integrity_issues: list[dict[str, Any]],
    notable_outcomes: list[dict[str, Any]],
    notable_summary: list[dict[str, Any]],
) -> str:
    planned = completion.get("planned_slots")
    attempted = completion.get("attempted_slots")
    stop_reason = completion.get("stop_reason")
    complete = planned is not None and attempted == planned and not stop_reason

    lines: list[str] = [
        "# Fulfillment Live Recovery Evaluation — Verified Analysis",
        "",
        f"Experiment directory: `{experiment_dir}`",
        "",
        "Automatically generated from experiment outputs",
        "",
        "## 1. Experiment integrity and accounting",
        "",
        md_table(
            ["Measure", "Verified value"],
            [
                ["Planned / attempted slots", f"{planned} / {attempted}"],
                ["Experiment complete", "YES" if complete else "NO"],
                ["Stop reason", stop_reason if stop_reason else "None"],
                ["Clean controls fully correct", f"{integrity_summary.get('clean_final_correct')} / {integrity_summary.get('clean_rows')}"],
                ["Faults activated", f"{integrity_summary.get('faults_activated')} / {integrity_summary.get('fault_rows')}"],
                ["Faults meaningfully exercised", f"{integrity_summary.get('faults_exercised')} / {integrity_summary.get('fault_rows')}"],
                ["API calls: trial sum / spend.json", f"{integrity_summary.get('summed_model_calls')} / {spend.get('api_calls_sent', 'N/A')}"],
                ["Input tokens: trial sum / spend.json", f"{integrity_summary.get('summed_input_tokens')} / {spend.get('provider_input_tokens', 'N/A')}"],
                ["Output tokens: trial sum / spend.json", f"{integrity_summary.get('summed_output_tokens')} / {spend.get('provider_output_tokens', 'N/A')}"],
                ["Unknown-usage calls", integrity_summary.get("unknown_usage_calls")],
                ["Incomplete model/tool/verification calls", f"{integrity_summary.get('incomplete_model_calls')} / {integrity_summary.get('incomplete_tool_calls')} / {integrity_summary.get('incomplete_verification_calls')}"],
                ["Workflow attempts / raw trace files", f"{integrity_summary.get('summed_attempt_count')} / {integrity_summary.get('raw_trace_files')}"],
                ["Estimated experiment cost", money(spend.get("estimated_cost_from_reported_usage_usd"))],
                ["Cross-file accounting errors", integrity_summary.get("source_crosscheck_errors")],
            ],
        ),
        "",
    ]
    if source_issues:
        lines.append("Cross-file validation found issues; see `integrity_issues.csv`.")
    else:
        lines.append("Cross-file validation passed for the checked fields in `trials.jsonl`, `trials.csv`, `paired.csv`, `plan.jsonl`, `summary.json`, `completion.json`, `spend.json`, and raw trace counts.")

    lines += [
        "",
        "## 2. Final correctness by fault class",
        "",
        "`Final correct` = completed run + task check passed + independent checker passed. Accidental and adversarial faults are kept separate.",
        "",
    ]
    class_rows: list[list[Any]] = []
    for fault_class in FAULT_CLASSES:
        for mode in MODES:
            r = next(x for x in by_class_mode if x["fault_class"] == fault_class and x["mode"] == mode)
            class_rows.append([fault_class, mode, r["eligible_pairs"], f"{r['final_correct_count']}/{r['eligible_pairs']}", pct(r["final_correct_rate"])])
    lines.append(md_table(["Fault class", "Mode", "Eligible n", "Final correct", "Rate"], class_rows))
    adversarial_faults = [r for r in by_fault if r.get("fault_class") == "adversarial"]
    if len(adversarial_faults) == 1:
        lines += ["", "The adversarial results come from one distinct fault schedule; `Eligible n` shows the number of repetitions included per mode."]

    lines += [
        "",
        "## 3. Fault propagation, affected stages, and policy-invalid actions",
        "",
        "`Affected stages` counts dependency-affected stages; `corrupted stages` counts stages independently observed as wrong. `Downstream corruption` means corruption reached a later stage. Action columns are total action counts, not percentages.",
        "",
    ]
    prop_rows: list[list[Any]] = []
    for fault_class in FAULT_CLASSES:
        for mode in MODES:
            r = next(x for x in by_class_mode if x["fault_class"] == fault_class and x["mode"] == mode)
            prop_rows.append([
                fault_class, mode, r["eligible_pairs"], pct(r["fault_exercised_rate"]),
                pct(r["agent_exposure_rate"]), pct(r["downstream_corruption_rate"]),
                num(r["mean_dependency_affected_stages"], 2),
                num(r["mean_observed_corrupted_stages"], 2), pct(r["controlled_interruption_rate"]),
                r["policy_invalid_attempts"], r["policy_invalid_executed"],
            ])
    lines += [
        md_table(
            ["Class", "Mode", "n", "Fault exercised", "Agent exposure", "Downstream corruption", "Mean affected stages", "Mean corrupted stages", "Controlled interruption", "Policy-invalid attempts", "Policy-invalid executed"],
            prop_rows,
        ),
        "",
        "A fault can be meaningful without downstream-agent exposure: verification may stop it first, a timeout may interrupt execution, or an Executor-stage fault may affect tools with no later agent.",
        "",
        "## 4. Fault-run resource effect relative to matched clean controls",
        "",
        "Each row uses matched pairs from the same case, mode, and repetition. `ΔX = X_fault − X_clean`; the reported value is the mean ± SD of those pairwise differences. Positive means the fault run used more; negative means it used less (for example, because execution stopped early).",
        "",
    ]
    resource_rows: list[list[Any]] = []
    for fault_class in FAULT_CLASSES:
        for mode in MODES:
            r = next(x for x in by_class_mode if x["fault_class"] == fault_class and x["mode"] == mode)
            resource_rows.append([
                fault_class, mode, r["eligible_pairs"],
                mean_sd(r["delta_model_calls_mean"], r["delta_model_calls_stdev"], 2),
                mean_sd(r["delta_tool_calls_mean"], r["delta_tool_calls_stdev"], 2),
                mean_sd(r["delta_verification_calls_mean"], r["delta_verification_calls_stdev"], 2),
                mean_sd(r["delta_reported_total_tokens_mean"], r["delta_reported_total_tokens_stdev"], 1),
                mean_sd(r["delta_e2e_latency_ms_mean"], r["delta_e2e_latency_ms_stdev"], 1),
                money(r["delta_estimated_cost_usd_mean"]),
            ])
    lines += [
        md_table(["Class", "Mode", "Matched n", "Δ model calls", "Δ total tools", "Δ verification", "Δ tokens", "Δ E2E ms", "Δ est. cost"], resource_rows),
        "",
        "`tool_calls` uses the experiment's agreed definition and includes verification calls.",
        "",
        "### Recovery work / wasted work",
        "",
        "Work-count values are averages over eligible fault runs. `Recomputed stages` counts stage types executed more than once in a logical trial. `Discarded` calls are failed, rejected, or superseded calls that did not contribute usable final work. Recovery latency is averaged only across runs that actually recorded recovery work (>0 ms).",
        "",
    ]
    work_rows: list[list[Any]] = []
    for fault_class in FAULT_CLASSES:
        for mode in MODES:
            r = next(x for x in by_class_mode if x["fault_class"] == fault_class and x["mode"] == mode)
            work_rows.append([
                fault_class, mode, r["eligible_pairs"], num(r["recomputed_stages_mean"], 2),
                num(r["recomputed_model_calls_mean"], 2), num(r["discarded_model_calls_mean"], 2),
                num(r["reported_discarded_tokens_mean"], 1), r["recovery_work_runs"],
                num(r["recovery_latency_when_positive_mean"], 1),
            ])
    lines += [
        md_table(["Class", "Mode", "n", "Recomputed stages", "Recomputed model calls", "Discarded model calls", "Discarded tokens", "Runs with recovery work", "Recovery latency ms"], work_rows),
        "",
        "## 5. Per-fault final correctness",
        "",
        "Each cell shows successful final-correct fault runs / eligible repetitions for that fault × mode.",
        "",
    ]
    fault_rows: list[list[Any]] = []
    for r in by_fault:
        def cell(mode: str) -> str:
            n = int(r.get(f"{mode}_eligible_n") or 0)
            rr = r.get(f"{mode}_final_correct_rate")
            successes = int(round(float(rr) * n)) if is_number(rr) else 0
            return f"{successes}/{n} ({pct(rr)})" if n else "N/A"
        fault_rows.append([r["fault_id"], r["fault_type"], r["fault_class"], r["stage"], cell("unprotected"), cell("full_restart"), cell("always_verify")])
    lines.append(md_table(["Fault", "Type", "Class", "Stage", "Unprotected", "Full restart", "Always verify"], fault_rows))

    lines += [
        "",
        "## 6. Clean-mode cost and overhead",
        "",
        "Absolute values below are averages over the clean runs recorded for each mode; `n` shows the denominator.",
        "",
    ]
    clean_abs_rows: list[list[Any]] = []
    for r in clean_metrics:
        clean_abs_rows.append([r["mode"], r["n"], num(r["model_calls_mean"], 2), num(r["tool_calls_mean"], 2), num(r["verification_calls_mean"], 2), num(r["nonverification_tool_calls_mean"], 2), num(r["reported_total_tokens_mean"], 1), num(r["e2e_latency_ms_mean"], 1), num(r["verification_latency_ms_mean"], 2), money(r["estimated_cost_usd_mean"])])
    lines += [
        md_table(["Mode", "n", "Model calls", "Total tools", "Verification", "Non-verif tools", "Tokens", "E2E ms", "Verification latency ms", "Est. cost"], clean_abs_rows),
        "",
        "For matched clean overhead, `ΔX = X_clean_mode − X_unprotected_clean` on the same case/repetition. Small token/latency differences can be normal live-call variability when call counts are unchanged.",
        "",
    ]
    clean_diff_rows: list[list[Any]] = []
    for r in clean_overhead:
        clean_diff_rows.append([
            r["mode"], r["matched_clean_controls"], mean_sd(r["delta_model_calls_mean"], r["delta_model_calls_stdev"], 2),
            mean_sd(r["delta_tool_calls_mean"], r["delta_tool_calls_stdev"], 2), mean_sd(r["delta_verification_calls_mean"], r["delta_verification_calls_stdev"], 2),
            mean_sd(r["delta_nonverification_tool_calls_mean"], r["delta_nonverification_tool_calls_stdev"], 2),
            f"{mean_sd(r['delta_reported_total_tokens_mean'], r['delta_reported_total_tokens_stdev'], 1)} (median {num(r['delta_reported_total_tokens_median'], 1)})",
            f"{mean_sd(r['delta_e2e_latency_ms_mean'], r['delta_e2e_latency_ms_stdev'], 1)} (median {num(r['delta_e2e_latency_ms_median'], 1)})",
            money(r["delta_estimated_cost_usd_mean"]),
        ])
    lines.append(md_table(["Mode vs unprotected", "Matched n", "Δ model", "Δ total tools", "Δ verification", "Δ non-verif tools", "Δ tokens mean±SD", "Δ E2E mean±SD ms", "Δ est. cost"], clean_diff_rows))

    lines += ["", "## 7. Repetition consistency", ""]
    repeated_groups = [r for r in variability if (r.get("eligible_pairs") or 0) >= 2]
    varied = [r for r in repeated_groups if is_number(r.get("final_correct_rate")) and 0.0 < float(r["final_correct_rate"]) < 1.0]
    if not repeated_groups:
        lines.append("This run does not contain at least two eligible repetitions per fault×mode group.")
    elif varied:
        lines.append(f"Final-correctness outcomes varied across repetitions for **{len(varied)}** of {len(repeated_groups)} repeated fault×mode groups.")
    else:
        counts = sorted({int(r.get("eligible_pairs") or 0) for r in repeated_groups})
        rep_text = str(counts[0]) if len(counts) == 1 else "/".join(str(x) for x in counts)
        lines.append(f"Final-correctness outcomes were consistent across all **{len(repeated_groups)}** fault×mode groups ({rep_text} eligible repetitions per group).")
    lines += ["", "`variability.csv` contains per-fault×mode means and SDs for resource/recovery measurements."]

    outcome_groups = [x for x in notable_summary if x.get("category") != "latency_outlier"]
    timing_groups = [x for x in notable_summary if x.get("category") == "latency_outlier"]
    lines += ["", "## 8. Review outcomes", ""]
    if outcome_groups:
        lines.append(md_table(
            ["Review label", "Fault", "Mode", "Count", "Reps", "Category", "Rule-based reason"],
            [[x["severity"], x.get("fault_id") or "-", x.get("mode") or "-", x.get("count"), x.get("repetitions") or "-", x["category"], x.get("representative_reason") or ""] for x in outcome_groups],
        ))
    else:
        lines.append("No outcome review flags were generated.")
    lines += ["", "These are rule-based review flags, not automatic exclusions.", "", "## 9. Timing notes", ""]
    if timing_groups:
        lines.append(md_table(
            ["Review label", "Fault", "Mode", "Count", "Reps", "Rule-based reason"],
            [[x["severity"], x.get("fault_id") or "-", x.get("mode") or "-", x.get("count"), x.get("repetitions") or "-", x.get("representative_reason") or ""] for x in timing_groups],
        ))
    else:
        lines.append("No >3×-median E2E latency notes were generated.")

    lines += [
        "",
        "## 10. Generated files",
        "",
        "- `summary.md` — human-facing verified report; start here.",
        "- `by_mode.csv` — pooled mode metrics for secondary/descriptive use.",
        "- `by_class_and_mode.csv` — class-separated correctness, propagation, resource, and recovery metrics.",
        "- `by_fault.csv` — one row per fault.",
        "- `by_mode_and_fault.csv` — detailed fault × mode measurements across repetitions.",
        "- `clean_metrics.csv` / `clean_overhead.csv` — clean-run cost and matched overhead.",
        "- `variability.csv` — repetition variability by fault × mode.",
        "- `integrity_issues.csv` — experiment/accounting issues only.",
        "- `notable_outcomes*.csv` — rule-based outcome review flags.",
        "- `review_queue.csv` — integrity + outcome review rows.",
        "- `analysis.json` — machine-readable analysis.",
        "",
        "Raw JSONL traces remain the underlying audit evidence.",
        "",
    ]
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    experiment_dir = args.experiment_dir.resolve()
    output_dir = (args.output_dir or experiment_dir / "analysis").resolve()
    if not experiment_dir.is_dir():
        raise SystemExit(f"Experiment directory does not exist: {experiment_dir}")

    trials = read_jsonl(experiment_dir / "trials.jsonl")
    pair_rows = read_csv(experiment_dir / "paired.csv")
    plan_rows = read_jsonl(experiment_dir / "plan.jsonl")
    trials_csv_rows = read_csv(experiment_dir / "trials.csv")
    completion = read_json(experiment_dir / "completion.json", {}) or {}
    spend = read_json(experiment_dir / "spend.json", {}) or {}
    runner_summary = read_json(experiment_dir / "summary.json", {}) or {}
    manifest = read_json(experiment_dir / "manifest.json", {}) or {}

    if not trials:
        raise SystemExit(f"No trial rows found in {experiment_dir / 'trials.jsonl'}")
    if not pair_rows:
        raise SystemExit(f"No pair rows found in {experiment_dir / 'paired.csv'}")

    output_dir.mkdir(parents=True, exist_ok=True)
    # Remove only known generated files so stale v1 artifacts cannot coexist misleadingly.
    for name in GENERATED_FILES:
        path = output_dir / name
        if path.exists() and path.is_file():
            path.unlink()

    source_issues, integrity_summary = validate_sources(
        trials, pair_rows, plan_rows, trials_csv_rows, completion, spend, runner_summary, experiment_dir
    )
    by_mode = analyze_by_mode(trials, pair_rows, spend)
    by_class_mode = analyze_by_class_and_mode(trials, pair_rows, spend)
    by_mode_fault = analyze_by_mode_and_fault(trials, pair_rows, spend)
    by_fault = analyze_by_fault(by_mode_fault)
    clean_metrics = analyze_clean_metrics(trials, spend)
    clean_overhead = analyze_clean_overhead(trials, spend)
    variability = analyze_variability(by_mode_fault)
    integrity_issues, notable_outcomes, review_queue = build_review_queue(trials, pair_rows, source_issues)
    notable_summary = summarize_notable_outcomes(notable_outcomes)

    analysis = {
        "schema_version": 2,
        "source_experiment_dir": str(experiment_dir),
        "experiment_complete": bool(
            completion.get("planned_slots") is not None
            and completion.get("attempted_slots") == completion.get("planned_slots")
            and not completion.get("stop_reason")
        ),
        "definitions": {
            "delta_symbol": "Δ means difference/change; the exact reference is table-specific",
            "pair_delta": "X_fault - X_matched_clean for same case/mode/repetition",
            "clean_overhead_delta": "X_clean_mode - X_unprotected_clean for matched clean controls",
            "mean_plus_minus_sd": "mean is the arithmetic average; SD is standard deviation across the relevant run-level observations",
            "median": "middle observation after sorting",
            "eligible_n": "number of valid matched pairs included in the calculation; requires a valid clean control, completed pair, and activated scheduled fault",
            "final_correct": "run_status == completed AND task_passed == true AND checker_passed == true",
            "fault_activated": "scheduled fault was actually injected/applied",
            "fault_exercised": "activated plus trace evidence of exposure, dependency impact, observed corruption, controlled interruption, or policy-invalid action",
            "agent_exposure": "at least one downstream agent received data influenced by the fault",
            "observed_corruption": "independent trace/evaluator evidence of an incorrect artifact, action, or state attributable to the fault",
            "downstream_corruption": "at least one later stage was independently observed as corrupted after the fault",
            "controlled_interruption": "fault intentionally interrupts execution, such as an injected timeout",
            "policy_invalid_attempted_executed": "authoritative action audit marked an invalid state-changing action as attempted / actually executed",
            "tool_calls": "experiment-defined total tool calls, including verification calls",
            "nonverification_tool_calls": "tool_calls - verification_calls",
            "recomputed_model_calls": "model calls repeated because recovery reran previously completed logical work",
            "recovery_latency": "elapsed time attributed to recovery from the known fault/recovery point to recovered logical-trial termination",
        },
        "completion": completion,
        "spend": spend,
        "integrity_summary": integrity_summary,
        "manifest_summary": {
            "kind": manifest.get("kind"),
            "backend": manifest.get("backend"),
            "seed": manifest.get("seed"),
            "repetitions": manifest.get("repetitions"),
            "modes": manifest.get("modes"),
            "dataset_file": manifest.get("dataset_file"),
        },
        "by_mode": by_mode,
        "by_class_and_mode": by_class_mode,
        "by_fault": by_fault,
        "by_mode_and_fault": by_mode_fault,
        "clean_metrics": clean_metrics,
        "clean_overhead": clean_overhead,
        "variability": variability,
        "integrity_issues": integrity_issues,
        "notable_outcomes": notable_outcomes,
        "notable_outcomes_summary": notable_summary,
    }

    write_csv(output_dir / "by_mode.csv", by_mode)
    write_csv(output_dir / "by_class_and_mode.csv", by_class_mode)
    write_csv(output_dir / "by_fault.csv", by_fault)
    write_csv(output_dir / "by_mode_and_fault.csv", by_mode_fault)
    write_csv(output_dir / "clean_metrics.csv", clean_metrics)
    write_csv(output_dir / "clean_overhead.csv", clean_overhead)
    write_csv(output_dir / "variability.csv", variability)
    write_csv(output_dir / "integrity_issues.csv", integrity_issues)
    write_csv(output_dir / "notable_outcomes.csv", notable_outcomes)
    write_csv(output_dir / "notable_outcomes_summary.csv", notable_summary)
    write_csv(output_dir / "review_queue.csv", review_queue)
    write_json(output_dir / "analysis.json", analysis)
    (output_dir / "summary.md").write_text(
        build_markdown(
            experiment_dir, completion, spend, integrity_summary, source_issues,
            by_mode, by_class_mode, by_fault, clean_metrics, clean_overhead,
            variability, integrity_issues, notable_outcomes, notable_summary,
        ),
        encoding="utf-8",
    )

    print(f"Analyzed {len(trials)} trial rows and {len(pair_rows)} clean/fault pairs.")
    print(f"Human-readable report: {output_dir / 'summary.md'}")
    print(f"Integrity issues: {len(integrity_issues)} -> {output_dir / 'integrity_issues.csv'}")
    print(f"Notable outcomes: {len(notable_outcomes)} -> {output_dir / 'notable_outcomes.csv'}")
    if completion:
        print(
            "Completion: "
            f"{completion.get('attempted_slots', '?')}/{completion.get('planned_slots', '?')} attempted; "
            f"stop_reason={completion.get('stop_reason')!r}"
        )
    return 1 if any(x.get("severity") == "ERROR" for x in integrity_issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
