# Step 3 re-evaluation using frozen baseline scoring

No model/API calls. No raw answers, prompts, workflow, injector, baseline labels or measurements changed. Original provisional artifacts remain in ../evaluation/. Revised artifacts are confined to this directory.

## Corrections

Five drafts change grounding and overall UNCERTAIN → FAIL: BASE-0003 clean iteration 1; BASE-0003 fault iteration 1; BASE-0007 clean iteration 1; BASE-0007 fault iterations 1 and 2. All add unsupported bank-processing instructions. BASE-0003 fault iteration 1 also asserts unsupported destination “to your account.” Frozen baseline v3 decisions already fail these categories; the previous pilot review incorrectly softened them. Every change is tied to a source section in label_changes.json.

All nine prior PASS drafts remain PASS after re-review. BASE-0006 clean remains FAIL for “a few days.” Two BASE-0007 login drafts remain UNCERTAIN pending adjudication of server-side “fixed” wording not explicitly settled in located baseline precedents. This is not an invented numeric-deadline exception or an inferred blanket server-side-fix rule.

## Aggregation

Unchanged run-level rule: use latest helper output per issue, including extras; all expected issues must be present and run completed. Record-alignment FAIL => DATA_ISSUE. For fully reviewed aligned outputs, any answer-criterion FAIL dominates UNCERTAIN; otherwise any UNCERTAIN => UNCERTAIN, otherwise PASS. Earlier attempts remain in all-draft statistics, not latest-output run scoring. All 8 runs completed with expected coverage and PASS record alignment. All-draft run aggregation is a separately labeled diagnostic, not replacement case scoring.

| Scope | PASS | FAIL | UNCERTAIN |
|---|---:|---:|---:|
| all_17_drafts | 9 | 6 | 2 |
| latest_14_issue_answers | 8 | 4 | 2 |
| latest_answer_8_runs | 4 | 4 | 0 |
| all_draft_8_runs_diagnostic_only | 3 | 5 | 0 |

All-draft counts: clean 4 PASS / 3 FAIL / 1 UNCERTAIN (8); fault 5 PASS / 3 FAIL / 1 UNCERTAIN (9). Latest-issue counts: clean 4/3/1 (8); fault 4/1/1 (6). Latest-answer run counts: clean 1 PASS / 3 FAIL; fault 3 PASS / 1 FAIL. Two uncertain login judgments remain visible even though a billing FAIL makes their runs FAIL.

| Case | Clean latest | Fault latest | Clean all drafts | Fault all drafts |
|---|---|---|---|---|
| BASE-0003 | FAIL | PASS | FAIL | FAIL |
| BASE-0004 | PASS | PASS | PASS | PASS |
| BASE-0007 | FAIL | FAIL | FAIL | FAIL |
| BASE-0006 | FAIL | PASS | FAIL | PASS |

BASE-0003 fault is latest-answer PASS but all-draft FAIL because its first billing draft fails. Do not discard that failed draft or interpret its later passing draft as proof of beneficial injection or recovery.

## Unchanged measured findings

All eight runs resolved within the four-iteration budget, without API errors or retries. Three eligible fault cases activated once at iteration 1, reached Router iteration 2 and revisited resolved work, then addressed the unresolved issue at iteration 3. The control skipped with no_missing_issue, not successful defense. Each activated case added one iteration, one helper/tool call and two model calls. Overall 34 model calls and 12,572 provider tokens. The exact per-pair calls/tokens/latencies and activation fields in paired_results.csv/json are copied unchanged and programmatically checked against the prior table. Raw usage remains under ../live/.

The pilot supports feasibility for a separately authorized larger activation/overhead experiment, not full-restart recovery or high task quality. Preserve natural baseline failures; adjudicate the uncovered login wording before quality claims. Four purposively selected cases, fixed clean-first order, simulated tools, model variability, no composed final customer answer and prior observer-context caveats remain limitations. No larger experiment was performed.

## Source status and deliverables

Read: frozen rubric_snapshot.json; v3 assessments_codex_preliminary.json and review_summary_codex_preliminary.md; human_review_tool/README.md and summarize aggregation; older v2 human review_state.json. The v3 files explicitly say preliminary and not human-validated. No finalized v3 human decisions were found in the workspace; this report does not relabel those sources as finalized. The user’s explicit unsupported-destination clarification agrees with the frozen rule and saved destination FAIL decisions.

Revised assessments, changes with supporting rules, human review, paired table, totals and preservation hashes are saved here. Original assessments, raw outputs, historical reviews and baseline labels are byte-identical. Run `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/workflow2_step3_pilot_local_20261102_120737/evaluation_frozen_rubric_revision/revise.py` for offline regeneration only.