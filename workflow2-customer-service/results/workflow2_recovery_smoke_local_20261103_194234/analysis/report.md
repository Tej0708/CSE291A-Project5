# Workflow 2 recovery smoke pilot analysis

**Recommendation: READY WITH CONDITIONS** for a larger diagnostic experiment, not a robustness claim.

Selected the newest directory with exactly 12 COMPLETED summary rows and corresponding completed results: `workflow2_recovery_smoke_local_20261103_194234`. The newer complete pilot supersedes earlier incomplete attempts for selection only; none were edited. Coverage is exactly NONE, QA_CORRUPTION, HELPER_CORRUPTION and TIMEOUT × unprotected, full_restart and always_verify, all BASE-0004.

## Outcome interpretation

All 12 executions ended normally and passed ledger/issue-coverage checks. That does not validate answer semantics or source-record integrity: unprotected helper corruption retains a contradictory record despite ledger resolution. Codex review finds 11 final-answer sets PASS and one FAIL, all provisional pending human review. Original UNREVIEWED labels and null recovery-success fields are preserved. Historical human adjudications were used as rubric precedents, not transferred to new answers. This analysis makes no human-finalized claims.

The failed retained billing answer in run 07 quotes a “possible reissue at $191.00 USD” and says “We're checking it against the authoritative billing ledger and will confirm the accurate amount”. The original scenario explicitly records a corrected/reissued USD 19 invoice. The model notices contradiction in prose, but no verification or follow-up action supports its promise. Grounding and coverage fail; unsupported ongoing action also fails status/responsibility. This is fault propagation through an aligned scenario, not a pre-existing DATA_ISSUE. Uncertainty language does not establish successful recovery.

All retained technical answers describe an available build 7.9.3 fix, installation through the existing channel, and Settings retest without claiming observed user-side repair. Other retained billing answers report the supported USD 19 correction. Run 01's “when you receive it” is treated as conditional review wording without a concrete delivery-channel/time guarantee; human review should confirm this interpretation. No unsupported refund timing/destination claims appear. Full quotes, all five criteria, exact event IDs, original labels, observed corrupted records and supporting clean records are in codex_reviews.json. Four discarded drafts are reviewed separately, including the failed billing draft before run 08's successful restart; they do not replace the final-output scoring rule.

## Activation and policy behavior

Every intended fault activated exactly once, confirmed by boundary values and subsequent consumers, not only mutation counts. Detailed before/after evidence is in trace_evidence.json; timelines.md provides all run timelines with exact event IDs.

- QA: iteration 1 changed OPEN `incorrect_invoice` to resolved `app_crash`, leaving an additional Router iteration. Unprotected and full_restart consumed this label and revisited the technical issue. They subsequently handled billing correctly. No QA verifier detected the injected label in these two modes; zero full restarts is expected because final record checks pass. Always_verify rejected `qa_ledger_mismatch` and regenerated QA before routing, avoiding that revisit.
- Helper: the billing record changed from corrected USD 19/authoritative to CONTRADICTORY USD 191/unverified/non-authoritative. Unprotected accepted it without a policy check; model acknowledgment of inconsistency is not detector success. Full_restart found `final_record_mismatch`, discarded attempt 1 and restarted once. Always_verify rejected the record before model prose generation and retried the helper with a fresh record once.
- Timeout: each trace's `on_tool_call` changes an actual successful app_crash tool record into `status=timeout, record=null`. The following helper_candidate contains the same injected value. Unprotected emits helper_unavailable, leaves the issue open and naturally routes back later. Full_restart triggers `helper_timeout` and restarts once. Always_verify rejects record_unavailable_or_mismatch and retries locally once. This is immediate synthetic status injection, not an actual five-second deadline, sleeping tool or provider timeout. A zero failed-business-tool-call count is expected: the successful service call is mutated after it returns.

`csa_workflow/recovery.py` implements terminal-record checks for full_restart and per-candidate helper/QA checks for always_verify. `faults.py` implements transient injection; `state.py` accepts supporting service evidence without requiring authority, explaining unprotected corrupted-record acceptance. Natural continuation is distinct from a measured policy repair interval; neither a successful clean run nor nonactivation counts as recovery. All invoked policy repairs completed in this sample; unprotected helper corruption was not recovered.

## Compact comparison

V = verification calls, R = full restarts, S = stage retries. No SDK retries (saved max_retries=0).

| Scenario | Policy | Activation | Codex final quality | V | R | S | Observed recovery |
|---|---|---|---|---:|---:|---:|---|
| NONE | unprotected | N/A | PASS | 0 | 0 | 0 | N/A: clean |
| NONE | full_restart | N/A | PASS | 2 | 0 | 0 | N/A: clean |
| NONE | always_verify | N/A | PASS | 4 | 0 | 0 | N/A: clean |
| QA_CORRUPTION | unprotected | CONFIRMED | PASS | 0 | 0 | 0 | Natural continuation; no policy recovery |
| QA_CORRUPTION | full_restart | CONFIRMED | PASS | 2 | 0 | 0 | Natural continuation; no policy recovery |
| QA_CORRUPTION | always_verify | CONFIRMED | PASS | 5 | 0 | 1 | Stage retry recovery (Codex-reviewed) |
| HELPER_CORRUPTION | unprotected | CONFIRMED | FAIL | 0 | 0 | 0 | Not recovered; no policy detection |
| HELPER_CORRUPTION | full_restart | CONFIRMED | PASS | 4 | 1 | 0 | Restart recovery (Codex-reviewed) |
| HELPER_CORRUPTION | always_verify | CONFIRMED | PASS | 5 | 0 | 1 | Stage retry recovery (Codex-reviewed) |
| TIMEOUT | unprotected | CONFIRMED | PASS | 0 | 0 | 0 | Natural continuation; no policy recovery |
| TIMEOUT | full_restart | CONFIRMED | PASS | 2 | 1 | 0 | Restart recovery (Codex-reviewed) |
| TIMEOUT | always_verify | CONFIRMED | PASS | 5 | 0 | 1 | Stage retry recovery (Codex-reviewed) |

## Accounting and observed overhead

All 59 application model calls match 59 observable provider dispatches, with no failed or incomplete model calls and no missing reported usage. All input/output/total fields reconcile to provider evidence. Calls, verification counts, combined tools, discarded calls, retries/restarts and event streaming reconcile to the ledger and summary. Current implementation hashes match the frozen run manifest. Python runtime floating-point summation differences are tolerated only within 1e-9 ms / 1e-12 relative error; counts and token values are exact. No material accounting inconsistency was found. Gateway-internal upstream attempts remain unobservable despite zero client SDK retries. Pricing, costs and original semantic-recovery judgments remain unknown/null; no USD estimate is made.

End-to-end is the recorded monotonic run endpoint; verification time includes nested fresh record reads, and repair time is an interval union. These categories overlap and must not be added. All attempts, including discarded attempt 1 in full restarts, contribute to the totals. Figure data are taken directly from these reconciled fields; values are rounded only for chart labels.

The table below compares each protected policy to unprotected within the same scenario. Percentage = 100 × (policy / unprotected − 1). Missing inputs or zero denominators yield null, not zero; none of these denominators is missing or zero. A negative latency difference is an observation, not demonstrated speedup. There is one serial run per cell, no counterbalancing, and network/service variation is unmeasured.

| Scenario | Policy | Tokens Δ | Tokens % | Calls Δ | Calls % | Latency Δ ms | Latency % |
|---|---|---:|---:|---:|---:|---:|---:|
| NONE | full_restart | -2 | -0.1 | +0 | +0.0 | -1335.2 | -52.6 |
| NONE | always_verify | -3 | -0.2 | +0 | +0.0 | -1149.2 | -45.3 |
| QA_CORRUPTION | full_restart | +0 | +0.0 | +0 | +0.0 | -158.8 | -7.4 |
| QA_CORRUPTION | always_verify | -604 | -26.3 | -1 | -16.7 | -562.3 | -26.3 |
| HELPER_CORRUPTION | full_restart | +1543 | +97.2 | +4 | +100.0 | +1387.9 | +80.2 |
| HELPER_CORRUPTION | always_verify | -95 | -6.0 | +0 | +0.0 | -354.3 | -20.5 |
| TIMEOUT | full_restart | -105 | -6.0 | +0 | +0.0 | -200.7 | -11.4 |
| TIMEOUT | always_verify | -254 | -14.4 | -1 | -20.0 | -337.4 | -19.1 |

Always_verify avoided a redundant helper generation in QA corruption (1695 versus 2299 tokens) and blocked corrupted helper prose before generation. Full restart repeated both issues in helper corruption (3130 tokens and 8 model calls versus 1587 and 4 unprotected), producing a correct final answer at higher observed work. These effects are specific to this case and deterministic verifier coverage, not evidence of general superiority. Clean controls use four model calls each, while verification adds tool work: combined tool calls 4/8/10 for unprotected/full_restart/always_verify. The unprotected clean latency was 2538 ms versus 1203/1389 ms in protected controls, illustrating why latency cannot be interpreted as deterministic policy cost here.

## Readiness conditions and limitations

The integration, mutation boundaries, logging and expected policy handling support expansion with conditions:

1. Human-review the new Codex judgments, including the conditional invoice wording; keep original labels and discarded drafts intact. Do not equate structural COMPLETED with final-answer PASS or policy recovery.
2. Preflight every added base case for valid records, reachable helpers and remaining iterations; log actual activation separately. Exclude unsuitable paired clean controls from conditional recovery claims.
3. Freeze the larger design, model settings and per-run/request ceilings before launch. Pricing is optional, but unknown costs mean there is no enforced USD spending bound. Do not silently extrapolate this pilot's token use into a dollar budget.
4. Retain the explicit simulated-timeout label. If the full experiment intends to test real deadline/cancellation/late-response behavior, add and separately validate that mechanism before making those claims; this pilot does not test it.
5. Interpret latency descriptively; counterbalance ordering and use repetition in the larger design if comparative latency is an objective. Do not modify baseline policy semantics to hide the observed unprotected failure.

No experiment-logic fix is required for the observed policy behavior. One base case with one run per cell cannot establish failure/recovery rates, statistical significance or general robustness. No significance tests or new experiments were performed.

## Deliverables and reproduction

- figures/outcome_matrix.png: provisional correct/incorrect/unreviewed final outcomes.
- figures/total_tokens.png, figures/model_calls.png, figures/e2e_latency_ms.png: grouped comparisons with consistent policy colors.
- run_comparison.csv: 12 consolidated rows, absolute and percentage overhead; blank CSV cost fields mean unknown.
- codex_reviews.json: separate Codex judgments and quoted evidence for retained and discarded drafts.
- trace_evidence.json and timelines.md: activation, detection and repair event references.
- validation.json: checks and hashes proving source artifacts unchanged.

Reproduce without provider calls from the repository root using the bundled Python with Pillow:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yanghede/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 results/workflow2_recovery_smoke_local_20261103_194234/analysis/analyze.py
```

The script only reads experiment data and writes analysis/. Reviews are explicit Codex assessments of this fixed run, not an automatic general-purpose semantic judge. No experiment labels or human adjudications are rewritten.
