# Saved pilot: Phase 1 evidence backfill v3

No provider calls or new semantic judgments. Original pilot and analysis/ hashes were checked unchanged. Automated fields use workflow2-phase1-v1; this directory is a separate versioned reduction. The earlier development backfills analysis_phase1_v1 and analysis_phase1_v2 are retained; use this v3 output.

The original 12 logical runs all completed. The previously saved Codex review (../analysis/codex_reviews.json) remains 11 provisional PASS and one FAIL: run 07 unprotected helper corruption. It is not human approval. This export leaves human verdicts/criteria blank and final quality UNREVIEWED rather than silently promoting those provisional judgments. Human review belongs after execution and user inspection.

All nine intended faults activated. QA unprotected/full_restart consumed the resolved app_crash label and reworked that issue; always_verify blocked it. Helper corruption propagated into an accepted USD 191 invoice record in unprotected/full_restart; full_restart then detected the mismatch and restarted, whereas always_verify blocked it before answer generation. TIMEOUT changed an actual ok app_crash record to timeout/null; unprotected took the unavailable branch and naturally continued, full_restart restarted, always_verify retried locally. This is synthetic status injection, not elapsed deadline handling.

Six of nine activated runs have explicit detector evidence: QA always_verify, helper full_restart/always_verify, and all three timeout policies (the unprotected timeout availability branch counts as recognition, not policy repair). The other three have no such detection: QA unprotected/full_restart and helper unprotected. These counts describe this sample only. Unknown recovery success remains null without scoped human review. Original policy intervals contain five triggered repairs: two full restarts and three stage retries See exact per-run intervals below; no pooled success rate is inferred.

| Slot | Consumption | Observed propagation | Affected types | Affected executions | Waste call union | Policy intervals |
|---|---|---|---|---:|---:|---:|
| 01_BASE-0004-NONE__unprotected | N/A | N/A | none observed | 0 | 0 | 0 |
| 02_BASE-0004-NONE__full_restart | N/A | N/A | none observed | 0 | 0 | 0 |
| 03_BASE-0004-NONE__always_verify | N/A | N/A | none observed | 0 | 0 | 0 |
| 04_BASE-0004-QA_CORRUPTION__unprotected | CONSUMED | PROPAGATED | helper, router | 2 | 6 | 0 |
| 05_BASE-0004-QA_CORRUPTION__full_restart | CONSUMED | PROPAGATED | helper, router | 2 | 6 | 0 |
| 06_BASE-0004-QA_CORRUPTION__always_verify | BLOCKED | DETECTED_CONTAINED | none observed | 0 | 1 | 1 |
| 07_BASE-0004-HELPER_CORRUPTION__unprotected | CONSUMED | PROPAGATED | helper | 1 | 0 | 0 |
| 08_BASE-0004-HELPER_CORRUPTION__full_restart | CONSUMED | PROPAGATED | helper | 1 | 8 | 1 |
| 09_BASE-0004-HELPER_CORRUPTION__always_verify | BLOCKED | DETECTED_CONTAINED | none observed | 0 | 2 | 1 |
| 10_BASE-0004-TIMEOUT__unprotected | CONSUMED | PROPAGATED | helper | 1 | 0 | 0 |
| 11_BASE-0004-TIMEOUT__full_restart | CONSUMED | PROPAGATED | helper | 1 | 3 | 1 |
| 12_BASE-0004-TIMEOUT__always_verify | BLOCKED | DETECTED_CONTAINED | none observed | 0 | 2 | 1 |

The waste union is an operational measurement, not final-answer correctness. QA revisit counts both superseded original producers and newly repeated producers, without duplicate IDs. Unprotected helper corruption has zero discarded/repeated calls even though the answer failed: this proxy does not capture all semantically wasted work. Unprotected timeout has no discarded producer because the service succeeded before middleware changed its returned status; later work is natural continuation. Missing partial-run ledgers are unknown, never manufactured zero work.

Unauthorized executed actions are N/A for all runs: tools read fixtures and documents; they do not execute invoice corrections/refunds or follow-up communications. The unsupported promise in run 07's answer is a semantic claim, not an executed unauthorized action. No adversarial cases were in this smoke pilot, though the dataset includes prompt-injection variants. Those must be analyzed separately in a future selected design.

measurements.json contains boundary before/after values, linked event/artifact/producer IDs, affected-execution details, wasted-work sets and tokens, original all-attempt metrics, and differences against unprotected and each policy's clean control. aggregate.json explicitly reports reviewed-clean denominator 0, clean UNREVIEWED count 3, activation 9/9, detection 6/9, no infrastructure errors, and no clean-success-conditional eligibility before review. Null costs remain null. Neither paired difference is equated to wasted work; overlap in verification/repair/e2e time is retained.

Readiness: the evidence/instrumentation supports future execution after completing the missing agreed larger-design configuration. It does not establish general recovery or robustness. Pending review is not an execution gate, but final conclusions require completed review. See ../../../phase1_v1/README.md and METRICS.md for definitions, full-design blockers, commands and reviewer procedure.
