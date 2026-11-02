# Workflow human review tool

A local, offline reviewer for saved `run_clean_audit.py` output. Python 3.9+ and a browser are sufficient. No packages, API keys, internet access, or model calls are required. All source code and UI text are English.

## Start

Extract `human_review_tool` into your project root. Keep `review_app.py` and `review.html` together. From the project root, activate your existing environment and select the exact completed run directory:

```bash
source .venv/bin/activate
python human_review_tool/review_app.py \
  --run-dir results/YOUR_COMPLETED_RUN_FOLDER \
  --reviewer Hede
```

Replace `YOUR_COMPLETED_RUN_FOLDER` with the real folder name. It must contain `case_results.jsonl`; keep its matching `manifest.json`, `summary.json` and case trace files alongside it when available. Do not combine files from different runs. The tool never defaults to the newest run or loads a dataset automatically.

The browser opens automatically. If it does not, open the printed `http://127.0.0.1:PORT/` address. Keep the terminal running. Stop with Ctrl+C. `--no-browser` disables automatic opening; `--port 8765` selects a fixed port.

## Review procedure

1. Check the original request, expected issues, automatic checks and QA history. Automatic checks are diagnostics, not human scores.
2. Read the observed tool record, any independent clean reference, support document and helper answer. A missing clean reference is explicitly shown; verify scenario facts independently where necessary.
3. Score the five criteria individually. No item starts as PASS. Record alignment is an environment/data assessment; the other four assess answer correctness.
4. Add a quote and reason for FAIL or UNCERTAIN. Save the current review, or choose **Save & next helper**. Partial reviews can be saved. Navigation warns before discarding unsaved edits.
5. Use case filters to find remaining work. Review every helper attempt; multi-issue cases have multiple tabs.
6. Export after completing review, or export an explicitly incomplete snapshot for discussion. The final success rate stays pending when cases are unreviewed, uncertain, or have data issues.

Use the same reviewer name and run directory to resume. Different reviewers get separate folders for independent assessment. Run only one server for a given reviewer/run combination. Multiple tabs in one server have revision guards. Source changes stop review to prevent mixing versions.

## Rubric: support-human-v1

| Criterion | PASS requirement |
|---|---|
| Record matches the scenario | The record fits this request and provides enough evidence for an appropriate response. A mismatch is DATA_ISSUE, not automatically model failure. |
| Answers the assigned question | Addresses this helper's specific issue. A billing helper need not solve an issue assigned to a technical helper. |
| Important claims have evidence | No unsupported material facts such as amounts, currency, refund deadlines, platforms or guarantees. |
| Includes necessary conclusions and steps | Provides the requested conclusion and necessary next steps; repeating every record field is unnecessary. |
| Accurate status and responsibility | Distinguishes an available fix from confirmed repair and avoids requiring another ticket for an issue already covered by this workflow. |

PASS / FAIL / UNCERTAIN / UNREVIEWED are available for every criterion. UNCERTAIN means the reviewer lacks enough evidence, not that the model truthfully described an uncertain situation. FAIL and UNCERTAIN require notes.

Examples:
- "If the problem persists after these steps, reply to this ticket" can PASS.
- "Open a new support ticket for your app crash" fails responsibility if that crash is already covered here.
- Omitting a technical issue from the billing helper's answer is not itself failure when another helper handles it.
- An evidence-backed installation instruction can satisfy the simulated task; it does not prove the user's device was repaired.

A helper answer passes only when all four answer criteria pass. Case success requires outputs for all expected issues and passing assessments for every latest issue output, including extra outputs. Missing helpers and unsuccessful runs fail. Earlier attempts remain in helper statistics; case scoring uses the latest attempt per issue. If earlier contradictory answers were actually shown to users, inspect the complete delivered conversation separately. This aggregation is intended for the current clean baseline, not certification of recovery after fault injection.

Structural checks remain separate. Record alignment is semantic, not exact field equality. No requirement is imposed that an intermediate record must match clean data before recovery can count. This tool cannot prove fault activation or validate external repairs.

Calibrate the rubric together on five cases, then freeze it. Have a second reviewer inspect failures and uncertain cases; keep independent scores. Do not rewrite bad model answers or remove failed samples to raise the baseline score.

## Saved results

Under the selected run folder:

```text
human_reviews/
  Hede_<reviewer_hash>/
    review_state.json
    export_<timestamp>_<id>/
      helper_reviews.csv
      case_reviews.csv
      human_summary.json
      review_summary.md
      rubric.json
      review_state.json
```

`review_state.json` is written atomically on Save and retains change history, reviewer, rubric version and input fingerprint. Exports are new snapshots. CSV files are Excel-compatible UTF-8 and guard against spreadsheet formula injection. The original `summary.json`, `answer_review.csv`, logs, source code and dataset are not modified. Do not edit exported CSVs expecting changes to flow back into the app.

`task_success_rate` is null until every case is adjudicated without uncertainty or data issues. `confirmed_case_pass_fraction` is only the confirmed-pass fraction so far, not a completed evaluation. Error cases remain in the denominator. A data issue must be resolved explicitly; it is not silently excluded. Model failures may legitimately remain in a clean baseline.

## Checks

```bash
python -m unittest discover -s human_review_tool -p 'test_*.py' -v
```

The tool reads saved helper outputs from `billing_service` and `technical_tool` evidence and structured helper events in the existing audit format. If your logger changes that schema, adapt the loader instead of interpreting missing text as a successful answer. It reads no `.env` file. The server binds only to loopback and has write-request token checks; do not expose it to a network.
