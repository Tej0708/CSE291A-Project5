# Workflow 2: GLM-assisted result analysis

Assessment coverage: 636/638 unique contexts. Accounted cost including all pilot versions and retries: $1.13121635; 748 paid requests. These are LLM assessments, not human approval.

The experiment remains 240 completed unique slots, with 180/180 fault scenarios activated. Five archived infrastructure attempts are separate. Original experiment statistics and the [Phase 1 requirements matrix](../analysis_offline_20261104_3d072433_en/PHASE1_REQUIREMENTS.md) remain authoritative for deterministic measures. No experiment was rerun.

| Scenario | Policy | Assessed / planned | LLM PASS / planned | FAIL | UNCERTAIN | DATA_ISSUE | Activated | Policy recovery triggered | PASS after policy recovery / triggered | Mean latency ms | Mean model calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HELPER_CORRUPTION | always_verify | 19/20 | 16/20 | 3 | 0 | 0 | 20 | 20 | 16/20 | 2752.3 | 4.00 |
| HELPER_CORRUPTION | full_restart | 20/20 | 15/20 | 5 | 0 | 0 | 20 | 20 | 15/20 | 4856.2 | 8.00 |
| HELPER_CORRUPTION | unprotected | 20/20 | 3/20 | 8 | 0 | 9 | 20 | 0 | N/A | 3118.7 | 4.00 |
| NONE | always_verify | 19/20 | 15/20 | 4 | 0 | 0 | 0 | 0 | N/A | 2031.0 | 4.00 |
| NONE | full_restart | 20/20 | 15/20 | 5 | 0 | 0 | 0 | 0 | N/A | 2188.4 | 4.00 |
| NONE | unprotected | 20/20 | 16/20 | 4 | 0 | 0 | 0 | 0 | N/A | 2103.2 | 4.00 |
| QA_CORRUPTION | always_verify | 20/20 | 14/20 | 6 | 0 | 0 | 20 | 20 | 14/20 | 2899.6 | 5.00 |
| QA_CORRUPTION | full_restart | 20/20 | 13/20 | 7 | 0 | 0 | 20 | 0 | N/A | 5629.8 | 6.00 |
| QA_CORRUPTION | unprotected | 20/20 | 13/20 | 7 | 0 | 0 | 20 | 0 | N/A | 3702.9 | 6.00 |
| TIMEOUT | always_verify | 20/20 | 13/20 | 7 | 0 | 0 | 20 | 20 | 13/20 | 2795.6 | 4.00 |
| TIMEOUT | full_restart | 20/20 | 18/20 | 2 | 0 | 0 | 20 | 20 | 18/20 | 2186.7 | 5.00 |
| TIMEOUT | unprotected | 20/20 | 13/20 | 7 | 0 | 0 | 20 | 0 | N/A | 2644.3 | 5.00 |

PASS-after-activation includes natural continuation; PASS-after-policy-recovery requires an actual policy recovery event. Neither is human-confirmed semantic recovery. Unassessed and UNCERTAIN results are explicit; neither is treated as FAIL. All clean runs have activation N/A. Recovery latency is averaged only over triggered policy recoveries in scenario_policy_results.csv; no trigger is not a zero-duration recovery.

## Main observations

HELPER_CORRUPTION has the largest observed separation: unprotected yields 3/20 combined LLM PASS, full_restart 15/20, and always_verify 16/20 with one unassessed run. Paired against unprotected, full_restart gains PASS on 12/20 cases and loses none; always_verify gains on 13/19 assessed pairs and loses none. These are LLM outcomes pending human review.

QA_CORRUPTION yields 13/20 PASS for unprotected and full_restart, versus 14/20 for always_verify. The first two policies do not trigger policy recovery in this scenario. TIMEOUT yields 13/20, 18/20 and 13/20 respectively; full_restart gains PASS on 6/20 pairs versus unprotected and loses on 1/20. Clean controls themselves yield 16/20, 15/20 and 15/20 PASS respectively, with one unassessed always_verify run. Fault-case differences cannot all be attributed to recovery because the clean answer-quality baseline is imperfect.

For HELPER_CORRUPTION, always_verify uses 4 model calls/run versus 8 for full_restart, with observed mean end-to-end latency 2752.3 ms versus 4856.2 ms. Against its own clean control, the mean latency increase is 721.3 ms (median paired increase 40.1 ms); full_restart increases by 2667.9 ms (median 2463.8 ms). These single-repetition descriptive results do not establish stable speedups. Full within-case comparisons for all three policy pairs are saved in paired_results*.csv.

Bundle-only assessment gives 180/240 PASS, while combining retained draft assessments with bundle coverage gives 164/240 PASS, 65/240 FAIL, 9/240 DATA_ISSUE and 2/240 unassessed. There are 19 bundle-versus-combined outcome differences in quality_disagreements.csv. The nine DATA_ISSUE outcomes occur in injected helper-corruption runs: reviewers should check whether the judge has conflated corrupted observations with a genuinely misaligned authoritative environment. Do not treat those classifications as confirmed dataset defects.

The two unresolved retained drafts are BASE-0027__NONE__always_verify__r1 (event bf263e2c-fab8-41f6-a310-b62f87f43207:49; non-exact answer quotation) and BASE-0007__HELPER_CORRUPTION__always_verify__r1 (event 4f7ef584-a85a-4845-8d5b-5316332da5a9:62; nonexistent evidence pointer). Both exhausted the configured two explicit retries. Review them directly; original experimental reruns are unnecessary.

## Interpretation and limits

The same case/scenario comparisons and each policy’s own clean control are in paired_results.csv and paired_results_summary.csv. Each group contains 20 distinct cases with one repetition each; latency differences are descriptive observations, not stable speedup or repeatability evidence. QA corruption can lead to natural continuation without a policy recovery event; do not rename it successful full-restart recovery.

The judge model is api-glm-5.3-flash, which also generated the original answers. Shared-model bias and LLM inconsistency limit independence. Exact quotes/source pointers are validated, but semantic judgments still require human review. Whole-run aggregation combines retained draft quality and independent bundle coverage; discarded drafts never lower delivered run quality. Archive bundles remain separate. Missing provider attempt usage and original experiment USD costs remain unavailable; the judge ledger does not retroactively estimate experimental charges.

## Human review and remaining work

Open priority_review_with_context.csv first. For each row compare user_question, original_records, observed_records and answers, then inspect the trace and exact criterion evidence. Fill the five human_* criteria and human verdict/reviewer/timestamp/rationale. Judge suggestions do not count as your decision. Then review complete_review_with_context.csv, including rows absent from the priority queue. human_followup_queue.csv also provides a reproducible PASS sample. Keep individual draft and final-bundle identities distinct.

- primary retained drafts: 480 total, 478 LLM-assessed, all human UNREVIEWED.
- primary discarded drafts: 80 total, 80 LLM-assessed, all human UNREVIEWED.
- infrastructure_archive retained drafts: 4 total, 4 LLM-assessed, all human UNREVIEWED.
- infrastructure_archive discarded drafts: 2 total, 2 LLM-assessed, all human UNREVIEWED.

The formal course rubric/submission format still requires confirmation because it was not found in the repository. Clean baseline and semantic recovery claims still await human review. Original run completeness requires no reruns. Any remaining judge errors are listed exactly in unfinished_items.csv; these are evaluation gaps, not failed experiments.
