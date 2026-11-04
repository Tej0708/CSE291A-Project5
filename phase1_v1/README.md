# Workflow 2 Phase 1 — ready to execute

The frozen design is 20 fault-applicable base cases × four scenarios (NONE, QA_CORRUPTION, HELPER_CORRUPTION, TIMEOUT) × three policies (unprotected, full_restart, always_verify) × one execution = **240 runs**. No live experiment was launched during preparation. Human review follows execution.

`full_config.json` is the agreed configuration; `full_manifest.json` contains the exact immutable 240-entry schedule and source/data hashes. `selected_population.json` records IDs, exclusions, eligibility criteria and coverage. The 20 QA-inapplicable rows are 20 distinct single-issue bases, not policy-expanded observations. All other 20 bases support all three faults structurally, so selection is a census, with no outcome filtering or sampling. These are fault-applicable cases, not necessarily representative of the original 40. All ten issue types remain represented, but every eligible case has a billing → technical expected route: no additional route diversity is available. Runtime classification can still prevent activation; activation remains a measured outcome.

BASE-0004 appeared in the recovery smoke pilot. BASE-0003, BASE-0004 and BASE-0007 also appeared in the earlier step-3 pilot. These are disclosed reused cases, not an unseen test population.

Execution is sequential. Seed 42 shuffles the sorted selected IDs. Each case runs its three clean controls first, then QA corruption, helper corruption and TIMEOUT; policy order rotates by case index. Every tuple occurs once. This is a single-repetition descriptive study: latency differences do not establish stable speedups.

Saved settings: api-glm-5.3-flash, temperature 0, other generation parameters omitted (provider defaults), 120-second timeout, zero SDK retries. Each case retains four iterations, 40 model / 40 tool / 40 verification dispatch limits, at most one full restart, and at most one retry per verified stage. The existing run-wide transient injector prevents reinjection on retries/restarts. TIMEOUT is synthetic status injection, not a measured provider timeout.

The inherited 150-request cap was a pilot-wide application cap, not a provider limit or a count of experimental runs. It remains the smoke runner default; full execution uses request_limit=null. Pricing is optional and unknown cost stays null. Provider limits are respected; provider failures are journaled and stop dispatch. Resume skips their terminal receipts and continues with the next scheduled tuple without retrying failed experimental runs.

## Run and resume

From the repository root:

```bash
RUN_DIR="results/workflow2_phase1_$(date +%Y%m%d_%H%M%S)"
.venv/bin/python workflow2_phase1.py execute --manifest phase1_v1/full_manifest.json --output "$RUN_DIR"
.venv/bin/python workflow2_phase1.py execute --manifest phase1_v1/full_manifest.json --output "$RUN_DIR" --resume
```

Keep RUN_DIR set to the same directory when resuming; in a new shell assign the actual prior path. Completed results are hash-checked and never overwritten. Resume is safe at inter-run boundaries and after logged provider failures. A mid-run interruption preserves partial evidence and refuses automatic replay, avoiding duplicate executions/reinjection. A killed process may leave `.execution.lock`; inspect that no process is running before removing the stale lock. Partial runs or failed sanity checks require an explicit protocol decision; do not delete evidence to rerun them. Analysis includes partial and unexecuted slots.

For offline preparation after an intentional source change, use `prepare --config phase1_v1/full_config.json --output NEW_MANIFEST.json`; existing manifests cannot be overwritten. Do not replace a manifest mid-experiment.

## Post-run analysis and human review

```bash
.venv/bin/python workflow2_phase1.py analyze --run-dir "$RUN_DIR" --output "$RUN_DIR"/analysis_phase1_v1
```

Copy analysis_phase1_v1/review_template.csv to a separate human_reviews.csv. After inspecting the run outputs, fill all five support-human-v1 criteria independently with PASS, FAIL, UNCERTAIN or UNREVIEWED, plus rationale, reviewer and review_timestamp. human_verdict is an optional annotation; authoritative aggregation follows the criteria, preserving the existing rubric. Review every retained issue, extras and discarded drafts; mark record alignment separately. Check original and observed corrupted records, exact answer quotes and trace IDs. Unsupported claims of completed repair, refund destinations/timing, or actions underway are not validated by structural success. Original model labels remain untouched. Existing human_review_tool/README.md provides criterion guidance; this CSV is a separate adapter, not a claim of compatibility with its legacy run-file loader.

```bash
.venv/bin/python workflow2_phase1.py analyze --run-dir "$RUN_DIR" --reviews "$RUN_DIR"/human_reviews.csv --output "$RUN_DIR"/analysis_phase1_human_v1
```

Aggregation validates answer hashes, event identities, criterion labels and reviewer metadata; never edits raw outputs or machine judgments. Missing review is UNREVIEWED, not PASS/FAIL. Outputs include all-draft review rows, latest-answer run quality, measurement evidence, two separately labeled paired differences, taxonomy-specific denominators and review provenance hash. Use a new output for every revision.

Saved-pilot backfill: results/workflow2_recovery_smoke_local_20261103_194234/analysis_phase1_v3. Existing analysis/ remains intact and its 11 PASS/1 FAIL provisional Codex review is not imported as human approval. The new automated export is deliberately unreviewed.


## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest test_phase1 test_recovery_smoke_pilot test_phase1_full -q
```

The full fixture blocks sockets, runs all 240 slots through the actual recovery/accounting runner with scripted model outputs, exceeds 150 provider dispatches, verifies one mutation per faulty run across restarts, resumes without modifying evidence, and exports/imports blank human review. Historical preparation snapshots (`preparation_manifest.json`, `full_config.template.json`, `preservation.json`, `tests.txt`) are retained as provenance; they do not supersede the finalized config or finalization test log.
