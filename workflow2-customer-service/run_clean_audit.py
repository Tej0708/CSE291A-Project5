"""Observe the existing clean workflow without changing agent decisions.

Run from the project root. All patches are scoped to one serial case.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import platform
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from csa_workflow import agents, orchestrator, services
from csa_workflow.dataset import load_cases
from csa_workflow.llm import OpenAIClient
from csa_workflow.state import WorkflowState
from csa_workflow.taxonomy import route_for


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


class Recorder:
    def __init__(self, path, case_id):
        self.file = path.open("x", encoding="utf-8")
        self.case_id = case_id
        self.started = time.perf_counter()
        self.stage = "initialization"
        self.iteration = 0
        self.issue = None
        self.calls = []

    def emit(self, event, **fields):
        row = {
            "case_id": self.case_id,
            "timestamp_utc": utc_now(),
            "elapsed_seconds": time.perf_counter() - self.started,
            "stage": self.stage,
            "iteration": self.iteration,
            "issue": self.issue,
            "event": event,
            **fields,
        }
        self.file.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.file.flush()


class ObservedOpenAI(OpenAIClient):
    """Preserve the supplied backend's request behavior and observe responses."""
    recorder = None

    def complete(self, system, user):
        recorder = self.recorder
        start = time.perf_counter()
        call_id = len(recorder.calls) + 1
        recorder.emit("llm_request", call_id=call_id, requested_model=self.model,
                      temperature=self.temperature, system_prompt=system, user_prompt=user)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            content = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            usage = usage.model_dump() if usage is not None else None
            entry = {
                "call_id": call_id,
                "status": "ok",
                "duration_seconds": time.perf_counter() - start,
                "returned_model": getattr(response, "model", None),
                "response_id": getattr(response, "id", None),
                "finish_reason": response.choices[0].finish_reason,
                "usage": usage,
            }
            recorder.calls.append(entry)
            recorder.emit("llm_response", **entry, response_text=content)
            return content
        except Exception as exc:
            entry = {
                "call_id": call_id, "status": "error", "usage": None,
                "duration_seconds": time.perf_counter() - start,
                "error_type": type(exc).__name__,
                "status_code": getattr(exc, "status_code", None),
            }
            recorder.calls.append(entry)
            recorder.emit("llm_error", **entry)
            raise


def independent_checks(case, result, initial_issues, helper_runs, reference):
    expected = set(case.expected_issues)
    actual = set(initial_issues)
    latest = {run["issue"]: run for run in helper_runs}
    issues_without_valid_records = []
    for issue in sorted(expected):
        run = latest.get(issue)
        valid = False
        if run:
            records = [e for e in run["workflow_events"]
                       if e["stage"] == "helper_result"]
            evidence = [e for e in run["new_evidence"]
                        if e["source"] in ("billing_service", "technical_tool")]
            valid = (
                run["route"] == route_for(issue)
                and bool(records) and bool(evidence)
                and records[-1]["record"] == reference[issue]["record"]
                and records[-1].get("verified") is True
                and evidence[-1]["verified"] is True
                and (route_for(issue) != "billing" or evidence[-1]["authoritative"] is True)
            )
        if not valid:
            issues_without_valid_records.append(issue)
    resolved_expected = all(result.issue_states.get(i) == "resolved" for i in expected)
    checks = {
        "expected_issues": sorted(expected),
        "initial_actual_issues": sorted(actual),
        "missing_issues": sorted(expected - actual),
        "extra_issues": sorted(actual - expected),
        "issue_set_match": expected == actual,
        "expected_issues_resolved": resolved_expected,
        "issues_without_valid_records": issues_without_valid_records,
        "structured_evidence_pass": not issues_without_valid_records,
        "status_match": result.final_status == case.expected_final_status,
        "within_iteration_budget": result.iterations <= case.max_iterations,
        "answer_correctness": "not_evaluated",
        "scenario_record_alignment": "requires_manual_review",
        "task_success": None,
    }
    checks["structural_pass"] = (
        checks["issue_set_match"] and resolved_expected
        and checks["structured_evidence_pass"] and checks["status_match"]
        and checks["within_iteration_budget"]
    )
    return checks


def run_one(case, client, output_dir):
    recorder = Recorder(output_dir / f"{case.case_id}.trace.jsonl", case.case_id)
    if client is not None:
        client.recorder = recorder
    initial_issues = []
    helper_runs = []
    reference = {i: asdict(services.call_tool(i, case_id=case.case_id, user_query=case.user_query)) for i in case.expected_issues}
    recorder.emit("case_input", case=case.raw, clean_reference_records=reference)
    original_decompose = agents.RouterAgent.decompose
    original_handle = agents._HelperAgent.handle
    original_review = agents.QAAgent.review
    original_tool = services.call_tool
    original_log = WorkflowState.log

    def decompose(agent, state):
        recorder.stage = "router_classification"
        start = time.perf_counter()
        original_decompose(agent, state)
        initial_issues.extend(state.issues)
        recorder.emit("classification_result", actual_issues=list(state.issues),
                      duration_seconds=time.perf_counter() - start)

    def handle(agent, issue_type, state):
        recorder.stage = f"{agent.route}_helper"
        recorder.iteration = state.iteration
        recorder.issue = issue_type
        start = time.perf_counter()
        issue = state.ensure_issue(issue_type)
        evidence_start = len(issue.evidence)
        history_start = len(state.history)
        try:
            return original_handle(agent, issue_type, state)
        finally:
            run = {
                "issue": issue_type, "route": agent.route,
                "iteration": state.iteration,
                "duration_seconds": time.perf_counter() - start,
                "new_evidence": [asdict(e) for e in issue.evidence[evidence_start:]],
                "workflow_events": copy.deepcopy(state.history[history_start:]),
            }
            helper_runs.append(run)
            recorder.emit("helper_completed", **run)

    def review(agent, state):
        recorder.stage = "qa"
        recorder.issue = None
        recorder.iteration = state.iteration
        start = time.perf_counter()
        feedback = original_review(agent, state)
        recorder.emit("qa_feedback", feedback=asdict(feedback),
                      issue_states={k: v.status.value for k, v in state.issues.items()},
                      duration_seconds=time.perf_counter() - start)
        return feedback

    def tool(issue_type, **context):
        start = time.perf_counter()
        result = original_tool(issue_type, **context)
        recorder.emit("raw_tool_result", issue=issue_type,
                      tool_result=asdict(result), tool_arguments={"issue_type": issue_type, **context},
                      duration_seconds=time.perf_counter() - start)
        return result

    def log(state, stage, **fields):
        original_log(state, stage, **fields)
        recorder.emit("workflow_event", workflow_stage=stage,
                      iteration=state.iteration, **fields)

    workflow_start = time.perf_counter()
    try:
        with patch.object(agents.RouterAgent, "decompose", decompose), \
             patch.object(agents._HelperAgent, "handle", handle), \
             patch.object(agents.QAAgent, "review", review), \
             patch.object(services, "call_tool", tool), \
             patch.object(WorkflowState, "log", log):
            result = orchestrator.run_case(case, llm=client)
        duration = time.perf_counter() - workflow_start
        checks = independent_checks(case, result, initial_issues, helper_runs, reference)
        report = {"case_id": case.case_id, "run_status": "completed",
                  "user_query": case.user_query, "result": asdict(result),
                  "checks": checks, "helper_runs": helper_runs}
    except Exception as exc:
        duration = time.perf_counter() - workflow_start
        report = {"case_id": case.case_id, "run_status": "error",
                  "error_type": type(exc).__name__,
                  "status_code": getattr(exc, "status_code", None),
                  "initial_actual_issues": initial_issues, "helper_runs": helper_runs,
                  "checks": None}
        recorder.emit("case_error", error_type=type(exc).__name__)
    calls = recorder.calls
    usage_complete = all(
        c["status"] == "ok" and c.get("usage") is not None
        and c["usage"].get("total_tokens") is not None for c in calls
    )
    report["metrics"] = {
        "workflow_seconds": duration,
        "llm_call_count": len(calls),
        "llm_seconds": sum(c["duration_seconds"] for c in calls),
        "usage_complete": usage_complete,
        "total_tokens": sum(c["usage"]["total_tokens"] for c in calls) if usage_complete else None,
        "observed_tokens": sum((c.get("usage") or {}).get("total_tokens") or 0 for c in calls),
        "helper_call_count": len(helper_runs),
    }
    recorder.emit("case_result", report=report)
    recorder.file.close()
    if client is not None:
        client.recorder = None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--llm", choices=["none", "openai"], default="none")
    parser.add_argument("--case")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-root", default="results")
    args = parser.parse_args()
    dataset_path = Path(args.path).resolve()
    cases = [c for c in load_cases(dataset_path) if c.fault_type == "none"]
    if args.case:
        cases = [c for c in cases if c.case_id == args.case]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        cases = cases[:args.limit]
    if not cases:
        parser.error("No clean cases matched the selection")
    if len({c.case_id for c in cases}) != len(cases):
        parser.error("Duplicate case IDs found")
    # Validate fixture alignment before spending API budget.
    for case in cases:
        scenario = services.scenario_for(case.case_id, case.user_query)
        if set(scenario["records"]) != set(case.expected_issues):
            parser.error(f"Fixture/expected-issue mismatch: {case.case_id}")
    # Construct the SDK client only when explicitly requested.
    client = ObservedOpenAI() if args.llm == "openai" else None
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    output_dir = Path(args.output_root).resolve() / f"clean_audit_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    code_files = sorted(Path(orchestrator.__file__).parent.glob("*.py")) + [Path(__file__)]
    manifest = {
        "run_id": run_id, "started_utc": utc_now(), "backend": args.llm,
        "requested_model": getattr(client, "model", None),
        "temperature": getattr(client, "temperature", None),
        "python_version": platform.python_version(),
        "dataset_filename": dataset_path.name,
        "fixture_filename": services.FIXTURE_PATH.name,
        "fixture_sha256": hashlib.sha256(services.FIXTURE_PATH.read_bytes()).hexdigest(),
        "fixture_schema_version": "2.0",
        "task_completion_definition": "Evidence-backed support response and applicable next steps; user-side repair is not observed",
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files},
        "case_ids": [c.case_id for c in cases],
        "notes": ["No API keys, headers, environment dump or endpoint URL are logged.",
                  "Durations include instrumentation; nested stage durations must not be added together.",
                  "LLM duration includes network, server work and SDK retries; it is not pure inference time.",
                  "Token usage is provider-reported; unknown usage is not zero.",
                  "Structural checks do not establish natural-language answer correctness.",
                  "Reference records come from authored scenario fixtures through the same service; semantic alignment and answers still require independent review."],
    }
    write_json(output_dir / "manifest.json", manifest)
    reports = []
    print(f"Output directory: {output_dir}", flush=True)
    with (output_dir / "case_results.jsonl").open("x", encoding="utf-8") as file:
        for case in cases:
            report = run_one(case, client, output_dir)
            reports.append(report)
            file.write(json.dumps(report, ensure_ascii=False) + "\n")
            file.flush()
            checks = report["checks"] or {}
            print(f"{case.case_id}: run={report['run_status']} "
                  f"structural_pass={checks.get('structural_pass')} "
                  f"missing={checks.get('missing_issues')} extra={checks.get('extra_issues')}", flush=True)
            if report["run_status"] == "error":
                print("Stopped after an error. Completed cases and partial traces are preserved.")
                break
    completed = [r for r in reports if r["run_status"] == "completed"]
    summary = {
        "selected_cases": len(cases), "attempted_cases": len(reports),
        "completed_cases": len(completed),
        "error_cases": len(reports) - len(completed),
        "structural_passes": sum(r["checks"]["structural_pass"] for r in completed),
        "issue_set_matches": sum(r["checks"]["issue_set_match"] for r in completed),
        "status_matches": sum(r["checks"]["status_match"] for r in completed),
        "workflow_seconds": sum(r["metrics"]["workflow_seconds"] for r in reports),
        "llm_calls": sum(r["metrics"]["llm_call_count"] for r in reports),
        "answer_correctness": "not_evaluated", "task_success_rate": None,
    }
    write_json(output_dir / "summary.json", summary)
    with (output_dir / "answer_review.csv").open("x", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["case_id", "user_query", "issue", "iteration", "tool_record",
                         "helper_answer", "record_matches_scenario", "answer_correct", "review_notes"])
        for report in reports:
            case = next(c for c in cases if c.case_id == report["case_id"])
            for run in report["helper_runs"]:
                records = [e["record"] for e in run["workflow_events"] if e["stage"] == "helper_result"]
                answers = [e["content"] for e in run["new_evidence"] if e["source"] != "support_doc"]
                writer.writerow([case.case_id, case.user_query, run["issue"], run["iteration"],
                                 json.dumps(records, ensure_ascii=False), "\n".join(answers), "", "", ""])
    print(json.dumps(summary, indent=2))
    print("Answer correctness remains pending manual review in answer_review.csv.")
    if len(completed) != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
