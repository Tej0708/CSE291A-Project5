# Workflow 2 formal QA-corruption experiment — frozen preparation

Status: prepared and validated offline. No formal run or model/provider request was made during preparation. This protocol measures activation and repeated-work overhead under the existing workflow; it does not implement or establish restart, always-verify, or semantic recovery.

## Frozen population and design

Selection is computed from `support_cases_unique40.jsonl`, using the existing expected-issue taxonomy: select NONE records whose issues include both technical and billing routes, then find their existing QA_CORRUPTION partners. The dataset has 200 rows, 40 base cases, and **20 mixed base cases**. Every pair has identical request text, expected issues and original iteration budget (4). No dataset, prompt, injector, historical label, or workflow decision was edited.

Selected base suffixes: 0003, 0004, 0007, 0008, 0011, 0012, 0015, 0016, 0019, 0020, 0023, 0024, 0027, 0028, 0031, 0032, 0035, 0036, 0039, 0040.

**40 planned runs = 20 clean + 20 qa_first_missing_once_v1.** Seed `20261102` shuffles sorted cases, then a list of ten clean-first and ten fault-first assignments using Python `random.Random`. The manifest stores the realized order, so execution does not depend on regenerating a shuffle. Pairs run adjacently and serially; each run constructs a fresh client, workflow state, injector and observer. No retries. Stop on the first runtime/provider error, retaining that error and every remaining not-attempted slot. No replacement of skipped/ineligible cases and no outcome-dependent reruns. A new execution after an interruption would require an explicitly documented protocol amendment, not silent replay.

Model and settings are copied from the successful pilot manifest: `api-glm-5.3-flash`, temperature 0.0; no other generation parameters supplied; provider defaults remain provider-controlled. Transport has zero retries and a 120-second timeout. Original per-case budgets are retained. Source, dataset, scenario-record, rubric, evaluation-rule and pilot-manifest hashes are frozen. Execution refuses drift and an existing output directory. Provider alias stability and external provider defaults cannot be guaranteed offline; returned model/response IDs are retained.

## Observation and result contract

`formal_observer.py` wraps the existing audit for serial use. It does not edit the agents, orchestrator, prompts, injector, datasets or historical runners/traces. Actual model and simulated tool invocations record stage, iteration, assigned issue, requests, responses/errors and elapsed time. Router input includes the actual feedback and ledger snapshot in **both** conditions; selection, resolved status, unresolved issues, and subsequent route/helper/no-helper actions are captured. Run/event/call IDs, dependency IDs and previous-event IDs connect QA boundary → Router receipt → selection → helper → tool → model. Injection boundaries are recorded as they occur, including before a later run error; the audit's original activation events remain available with links to those trace events. Stage-local model/tool errors are preserved even though a top-level error has no completed RunResult.

Provider usage is retained as the complete returned object, including nested provider details. Token aggregates expose exact total, known subtotal and missing-call count separately. A missing usage object or token field yields a null total; observed zero stays zero; no calls yields zero. Elapsed time includes observer overhead and must be described as observed end-to-end time. Tool calls are counted at invocation, not inferred from helper success logs.

Schemas in this directory describe trace events, raw run results, per-run metrics, paired deltas, draft assessments and latest-answer quality. Additional provider fields are preserved. The offline evaluator emits:

- `metrics.json`: eligibility, skip reason, mutation count, Router receipt, repeated helper/tool calls, post-mutation stages, subsequent genuinely unresolved work, ledger status, iteration/model/tool totals, provider tokens, elapsed time and errors. Clean eligibility is null (not applicable). On errors, raw `injection_boundaries` preserve available partial observations; unavailable derived activation measures remain unknown.
- `paired_results.json`: fault-minus-clean iteration/call/token/time differences for completed pairs; unavailable or missing-usage deltas stay null. Keep all 20 pairs, including incomplete pairs.
- `assessment_template.json`: every helper draft starts UNREVIEWED, with reviewer/provenance, quotes, rule references and notes. Draft IDs link to original request, observed tool records, support evidence and raw traces. Fill a separate copy; never rewrite raw answers.
- `all_draft_quality.json`: every attempt, including superseded answers and extra issues. `quality_summary.json` reports these helper counts separately.
- `latest_answer_quality.json`: latest answer **per issue including extras**, expected coverage, completion and record-alignment checks using the existing review-tool aggregation. Ledger resolution never substitutes for quality. There is no composed final customer answer.

Apply `BASELINE_EVALUATION_RULES.md` and the frozen support-human-v1 rubric symmetrically. Evaluate all five criteria independently. Unsupported refund timing/destination and unsupported definite repair claims fail under the documented boundaries; do not penalize supported build-level fixes or recorded interventions solely for missing user confirmation. Record-alignment failure is DATA_ISSUE. Missing helpers/unsuccessful runs fail; incomplete reviews and uncertainty remain explicit. Retain assessment provenance: prior Codex judgments are not human-finalized. No semantic model judge is used. Any new adjudication must be a separate revision with source, scope, reason and prior labels retained.

Analysis denominators: report 20 planned fault slots, attempted/completed counts, eligible counts, mutated counts, unchanged Router receipts, repeated actions and skipped reasons separately. Report mutation/eligibility and receipt/mutation ratios with explicit denominators; do not turn skips into defense successes. Preserve all 40 slots for quality/accounting. Report paired overhead descriptively, stratifying activated/consumed versus skipped; one stochastic run per condition is not a causal population estimate. Post-mutation stages are temporal observations, not automatically causally affected stages. Attribution requires the linked repeated-action evidence plus the clean comparison. Subsequent unresolved work is continuation, not full restart.

## Commands

Run from the repository root. No credentials are needed for validation, verification or evaluation.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s human_review_tool -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py verify
```

The review HTTP test needs permission to bind a loopback server; it makes no model/external provider calls. The frozen manifest is already prepared. To reproduce it into a new file without overwriting the freeze:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py prepare --output /tmp/workflow2-manifest-reproduction.json
```

**Future execution only after authorization — NOT run in this task:**

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py execute --output results/workflow2_formal_v1
```

Offline evaluation after execution (new output directories each time):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py evaluate --run-dir results/workflow2_formal_v1 --output results/workflow2_formal_v1/evaluation_unreviewed
# Copy assessment_template.json to a new assessments.json; review every draft with the frozen rules.
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py evaluate --run-dir results/workflow2_formal_v1 --assessments results/workflow2_formal_v1/assessments.json --output results/workflow2_formal_v1/evaluation_reviewed
```

## Remaining Phase 1 checklist

- [x] Read final user-adjudicated pilot report and frozen evaluation rules; retain historical results and labels.
- [x] Correct formal observation context, symmetric Router evidence, dependency links and nullable usage.
- [x] Compare unchanged requests/results/activation in 160 paired plain/observed fixture comparisons (40 base cases × two conditions × two issue orders; 320 workflow executions), plus isolation, errors, skipped injection and provider-request fixtures.
- [x] Validate the 40-slot manifest and offline extraction/quality separation with scripted fixtures; run existing workflow and review tests.
- [x] Freeze 20 pairs, order/seed, settings/budgets, schemas and commands; keep formal outputs separate.
- [ ] Obtain explicit authorization for live formal execution. Offline preparation has no unresolved implementation blocker.
- [ ] Execute exactly the frozen schedule; retain errors, not-attempted slots and skips. Do not replace outcomes.
- [ ] Inspect receipt/dependency integrity and missing usage, then independently review all drafts and latest-per-issue answers under the frozen rules; retain reviewer provenance and separate adjudication revisions.
- [ ] Publish descriptive paired activation/overhead and separate ledger/latest/all-draft quality results with all denominators and limitations.
- [ ] Decide any later Phase 1 follow-up from those results. Restart and always-verify remain separate future work requiring their own implementation and matching evaluations.
