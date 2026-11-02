# Step 3: bounded live-model pilot — blocked

The pilot does **not yet support proceeding to a larger experiment**. The first clean classification request failed with `APIConnectionError`. The runner stopped immediately, without retries or model substitution. Connectivity failed before a response was available; authentication and model availability were not verified. The underlying connection cause is unavailable in the intentionally sanitized error record. No credentials or endpoint details were printed.

## Selection and settings

Selection was saved before any live request in selected_case_manifest.json: BASE-0003 (duplicate charge/app crash), BASE-0004 (incorrect invoice/app crash), BASE-0007 (charge after cancellation/login failure), and BASE-0006 (single duplicate-charge control). Existing NONE and QA dataset variants were used unchanged. Each pair has identical customer input and four-iteration budget; the only behavioral condition change is the existing opt-in qa_first_missing_once_v1 profile. Dataset variant IDs differ as recorded; fixture selection normalizes to the same base case. No classification order was imposed.

The matching v3 full baseline manifest identifies `api-glm-5.3-flash`, temperature `0.0`. Requests use the same two-message chat completion format and omit other generation parameters, as the baseline does. Provider defaults remain unspecified. Transport was explicitly bounded to zero retries and a 120-second timeout; these are transport settings, not generation changes. The provider returned no model identity or usage.

## Execution and paired results

| Case | Clean | Fault | Activation / routing / quality |
|---|---|---|---|
| BASE-0003 | Classification APIConnectionError | Not attempted | Unavailable |
| BASE-0004 | Not attempted | Not attempted | Unavailable |
| BASE-0007 | Not attempted | Not attempted | Unavailable |
| BASE-0006 | Not attempted | Not attempted | Unavailable |

One workflow execution was attempted; seven were not attempted. One model request was attempted; zero retries, helper calls, and simulated tool calls occurred. End-to-end elapsed time was 1.2819 seconds; the failed model call took 1.2793 seconds. Provider token usage is missing (null), not zero. No complete clean/fault pair exists, so all paired deltas are unavailable. No final status or iteration total was produced. This is a pre-routing error, not an ineligible-injection skip or successful defense. There is no activation denominator from completed live fault runs.

No live answer exists for rubric review. HUMAN_REVIEW.md explicitly records both unavailable answers and available trace evidence for each selected case; provisional_assessment.json preserves the baseline rubric and marks all cases UNREVIEWED. No task completion, repeated work, unresolved-work handling, recovery, or answer-quality claim is supported. Full restart and always-verify were not run.

## Preservation and observation

Only a separate run_live_pilot.py runner was added. It reuses the existing audit injector instrumentation and baseline model observer, and adds read-only workflow/tool/QA-state snapshots. Source and dataset hashes are in the selection manifest; run metadata is embedded in each raw trace. All 251 inventoried pre-existing source/data/result/review artifacts remained byte-identical (preservation_check.json). Credentials, Git internals, caches and .DS_Store were excluded from the inventory. Existing working-tree changes were not reverted.

The existing 26-test root suite passed. Before execution, all eight selected offline scripted conditions produced exactly the same workflow result/history and mutation counts with and without the new observer (observer_validation.json). Those scripted traces are isolated under offline_validation/ and are not live evidence. No model-generated classifications are replaced with expected labels in live runs.

Model-generated decisions: initial issue classification, helper answer prose, and QA candidate labels when unresolved issues exist. Deterministic decisions: classifier validation/fallback, Router selection, simulated tools, evidence acceptance, QA label validation and reason normalization, injector eligibility/replacement, and termination. The Router is deterministic code, so future activation would demonstrate model-assisted workflow susceptibility, not a separate Router model choosing to obey an injected instruction.

The workflow has no final answer-composition stage. Successful future observations would preserve every helper answer and expose the latest answer per issue without rewriting or synthesizing a customer answer. This run generated neither.

## Artifacts and next step

- selected_case_manifest.json and reproduce.sh: pre-execution selection, settings, hashes and exact command targeting a fresh directory.
- live/BASE-0003-NONE/trace.jsonl: ordered request/error trace and run metadata.
- live/BASE-0003-NONE/usage.json and result.json: failed-call timing, missing provider usage and runtime outcome.
- paired_results.csv / paired_results.json: one row per selected case, with unavailable comparisons explicitly represented.
- HUMAN_REVIEW.md / provisional_assessment.json: review evidence and unavailable quality assessment.

Resolve connectivity before a newly authorized bounded pilot. Do not expand to the full dataset on this evidence. The recorded reproduction command is documentation, not an automatic retry. Even a completed future pilot would remain exploratory: independent live executions can vary, skipped injection is not defense, and task completion after injection is not proof of full-restart recovery.
