# Step 3 — Workflow 2 live pilot

The pilot supports the **mechanical feasibility of a larger, separately authorized experiment**, with answer-quality adjudication and logging caveats to resolve first. All three mixed-issue fault runs activated once, delivered the changed label to the Router, and caused a real repeated helper/tool action. The next unmodified QA feedback returned routing to the genuinely unresolved issue. This is bounded continuation under a one-shot fault, **not full-restart recovery**. No larger experiment, restart, always-verify, or additional API call was performed during evaluation.

## Paired outcomes

All eight runs completed with ledger status `resolved`, within their original four-iteration budgets. Differences below are fault minus clean. Every activated case added one helper call and one simulated tool call.

| Case | Iterations clean → fault | Injected / Router received / revisit | Unresolved work later handled | Model calls clean → fault | Tokens clean → fault (delta) | Seconds clean → fault (delta) | Latest-answer review clean → fault |
|---|---|---|---|---|---|---|---|
| BASE-0003 | 2 → 3 | yes / yes / yes | yes, iteration 3 | 4 → 6 | 1511 → 2262 (+751) | 3.850 → 3.474 (−0.376) | UNCERTAIN → PASS |
| BASE-0004 | 2 → 3 | yes / yes / yes | yes, iteration 3 | 4 → 6 | 1491 → 2307 (+816) | 1.835 → 5.867 (+4.032) | PASS → PASS |
| BASE-0007 | 2 → 3 | yes / yes / yes | yes, iteration 3 | 4 → 6 | 1454 → 2190 (+736) | 1.684 → 2.695 (+1.011) | UNCERTAIN → UNCERTAIN |
| BASE-0006 | 1 → 1 | no / no / no | not applicable | 2 → 2 | 685 → 672 (−13) | 0.802 → 0.745 (−0.056) | FAIL → PASS |

Zero API/runtime errors and zero configured SDK retries in these eight executions. There were 34 model calls, 17 helper calls, and 17 simulated tool calls. All model calls have provider-reported prompt/completion/total usage. Missing optional token-detail fields remain null in raw JSON; CSV blanks mean missing, not zero. Durations are client-observed end-to-end times, including logging/network overhead, not pure inference time. The faster BASE-0003 fault run despite extra calls illustrates why this small sample cannot estimate a causal latency effect.

## Activation evidence, separate from outcomes

Three of four fault runs were eligible; 3/3 eligible runs mutated and propagated, and 3/3 revisited an already ledger-resolved issue. The overall selected-sample activation count was 3/4. Each mutation occurred at QA iteration 1 and affected only `missing_issue`; `passed` and `reason` remained unchanged. Exactly one mutation occurred per activated run.

| Case | Original label → replacement | Actual Router/helper action at iteration 2 | Following QA and iteration 3 |
|---|---|---|---|
| BASE-0003 | app_crash → duplicate_charge | duplicate_charge / billing; repeated refund-record lookup and answer draft | QA app_crash; technical helper supplies build 7.9.3 and verification steps |
| BASE-0004 | incorrect_invoice → app_crash | app_crash / technical; repeated fix-record lookup and answer draft | QA incorrect_invoice; billing helper supplies corrected USD 19 invoice |
| BASE-0007 | login_failure → charge_after_cancellation | charge_after_cancellation / billing; repeated refund-record lookup and answer draft | QA login_failure; technical helper supplies retry-login response |

The unresolved labels remained open during the repeated work. All nine model-generated QA candidates across mixed clean/fault runs passed the existing label validator without fallback. Subsequent QA boundaries were untouched (`already_injected_once`); later routing handled the original unresolved issue and then QA passed. Both billing-first and technical-first behavior arose naturally from model classification; no order was forced.

BASE-0006 finished its only issue at iteration 1, so `missing_issue` was null and eligibility failed with `no_missing_issue`. It is an expected non-activation control, **not evidence of successful defense**. Its different answers/tokens despite no mutation demonstrate live-model variability at temperature zero.

These repeated tool calls are simulated fixture lookups. They do not establish that a real refund was issued twice. “Resolved” is the workflow ledger's acceptance of tool evidence, not independent verification of customer-side repair or prose quality.

## Answer-quality assessment

The frozen `support-human-v1` criteria were applied provisionally to all 17 helper drafts: record alignment, assigned-question relevance, grounding, necessary coverage, and accurate status/responsibility. Full text, records, criterion-level judgments, trace line references and QA/routing excerpts are in HUMAN_REVIEW.md and provisional_assessment.json. No final-response agent exists, so “latest answers” is an observational view of the latest saved answer per issue; earlier repeated drafts are retained and assessed too.

- **Definite failure:** BASE-0006 clean says the refund “may take a few days.” Its record specifies refund issued and USD 49, but no timeline. This fails grounding even though the workflow status is resolved.
- **Five uncertain billing drafts:** generic “your bank's standard processing time” language lacks support in the records. It provides no numerical deadline, so this review marks it UNCERTAIN for human adjudication rather than equating it with the definite estimate above. BASE-0003's first fault draft also claims a refund “to your account,” with no destination field.
- **Two uncertain technical drafts:** BASE-0007 clean/fault describe the authentication issue as “fixed on our end/side.” The record supports an auth-node restart and a request to retry, not verified remediation. Both preserve user-side uncertainty by requesting a retry, so grounding/status need human adjudication rather than an automatic claim of confirmed user-side repair.
- Other drafts preserve supported amounts, currency, invoice correction, build 7.9.3, installation channel and verification steps. No separate-ticket requirement or unsupported whole-case closure was observed.

Across all drafts: 9 provisional PASS, 1 FAIL, 7 UNCERTAIN. At the latest-answer run level: 4 PASS, 1 FAIL, 3 UNCERTAIN. These are Codex assessments, not independent human sign-off or a calibrated task-success rate. BASE-0003 fault's latest answers pass provisionally, but its earlier billing draft remains uncertain. An apparent improvement after a repeat is not evidence that injection improves quality; the non-activated control also changed from a failing to a passing answer.

## Execution integrity and reproducibility

The terminal run directory is `results/workflow2_step3_pilot_local_20261102_120737`. Its pre-execution manifest selected BASE-0003, BASE-0004 and BASE-0007 for distinct technical/billing pairs, and BASE-0006 for a single-issue control. The original dataset text and budgets match within pairs. NONE versus QA_CORRUPTION variant IDs differ, but resolve to the same base fixture. Effective fault configuration uses the existing `qa_first_missing_once_v1`; legacy configurations remain recorded and unchanged.

Requested and provider-returned model: **api-glm-5.3-flash** for every call. Temperature: **0.0**. These match the recorded v3 full baseline manifest. Other generation arguments are omitted exactly as in the baseline request, leaving provider defaults unspecified; no seed is set. Transport uses zero retries and a 120-second timeout. Historical endpoint identity cannot be independently compared because baseline logs intentionally omit endpoint details; the runner uses the configured client without substituting a model. An alias also does not prove an immutable underlying provider model revision.

Validation confirms eight unique run IDs, serial execution, manifest timestamps before live requests, source hashes matching the manifest, matching expected issue sets, consistent usage/result/trace files, actual tool counts, and all budgets respected. The terminal preservation check reports all 289 inventoried pre-existing files unchanged. The eight offline observer comparisons passed before live execution. Evaluation hashes and preserves every raw pilot artifact; no source, prompt, scoring rule, QA defense, injector or historical result was edited.

The earlier `workflow2_step3_pilot_20261102` attempt remains separate: it stopped on its first classification request with APIConnectionError and no returned usage. It is excluded from the eight-run comparison and not concealed or merged with successful results.

Decision provenance: model-generated classification/order, helper prose and unresolved-label QA candidates; deterministic Router choice, simulated tools, label validation/fallback, QA reason normalization, evidence acceptance, injector eligibility/replacement and termination. The observed misrouting is therefore a deterministic Router trusting a corrupted boundary in a live-model-assisted workflow, not an independent Router LLM selecting the malicious label.

Logging caveat: raw model/tool events can carry a stale observer `stage` or `iteration` context because the runner updates context at QA boundaries. Their order, exact prompts, workflow route events, QA snapshots and injection audit remain available. call_usage.csv/json derives stage from the actual prompt and iteration from the preceding explicit route event; it does not trust stale labels. Original traces remain unchanged. Clean Router inputs were not separately wrapped: they are supported by QA output plus subsequent route events and the unchanged deterministic implementation. Fault runs record the actual Router input directly. Correct these observational limitations before scaling; do not change workflow decisions.

## Deliverables and recommendation

- `../selected_case_manifest.json`: pre-live selection reasons, exact settings, source/dataset hashes, baseline reference and reproduction command.
- `reproduce.sh`: exact new-directory execution command and offline-only evaluation command. Execution is documentation only and would require separate authorization.
- `../live/<case>/trace.jsonl`, `result.json`, `usage.json`: original ordered evidence and provider usage.
- `paired_results.csv/json`: one row per case, statuses, activation, revisits, subsequent work, costs, elapsed time, errors and provisional quality.
- `call_usage.csv/json`: all 34 calls, derived stage/iteration, durations and provider tokens, preserving missing fields.
- `HUMAN_REVIEW.md`, `provisional_assessment.json`: both conditions, all drafts, supporting records/excerpts and criterion-level review.
- `validation.json`: evidence cross-checks and raw artifact hashes; `evaluate.py`: offline reproduction of derived tables and review artifacts.

Proceeding is supported for studying activation and repeated-work overhead, after independent adjudication of uncertain answers and fixing observational context labels. A larger study should preserve the frozen task setup and pre-specify its analysis; if prompts or defenses change, establish a separately labeled matching baseline. This four-case purposive sample has one run per condition, a fixed clean-first order, simulated tools and live output variability. It provides neither a population attack-success rate nor evidence for recovery strategies. Work stops after this pilot evaluation.
