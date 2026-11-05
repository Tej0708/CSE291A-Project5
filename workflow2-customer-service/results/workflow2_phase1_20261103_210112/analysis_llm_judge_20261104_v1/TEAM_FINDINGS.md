# Workflow 2: findings and delivery status

## What is complete

The frozen design is **20 cases × 4 scenarios × 3 policies × 1 repetition = 240 unique experimental slots**. All 240 are completed and pass execution-integrity verification. Failed, error, budget_exhausted, partial and not_run counts are zero; there are no missing, duplicate or extra experimental slots. All 180 fault scenarios activated. Five archived infrastructure attempts are separate from these 240 slots.

The saved-answer assessment used **api-glm-5.3-flash through TritonAI**. It produced valid assessments for **809/811 review items**, mapped from **636/638 unique contexts**. All 240 final bundles were assessed; two retained individual drafts remain unresolved. The cumulative tariff-accounted cost is **$1.13121635 for 748 requests**, including abandoned pilot calls, invalid responses and retries. No experimental cases were rerun.

## Main results

These are **LLM-assessed combined run outcomes**, combining retained draft assessments with independent bundle coverage. They are not human approvals.

| Scenario | Unprotected PASS | Full restart PASS | Always verify PASS |
|---|---:|---:|---:|
| Clean (NONE) | 16/20 | 15/20 | 15/20; 1 unassessed |
| QA corruption | 13/20 | 13/20 | 14/20 |
| Helper corruption | 3/20 | 15/20 | 16/20; 1 unassessed |
| Timeout | 13/20 | 18/20 | 13/20 |

Across all 240 runs: **164 PASS, 65 FAIL, 9 DATA_ISSUE and 2 unassessed**. Bundle-only assessment gives 180/240 PASS; there are 19 differences between bundle-only and combined outcomes. See quality_disagreements.csv rather than treating those methods as interchangeable.

- **Helper corruption shows the largest observed separation.** Against unprotected on the same cases, full_restart gains PASS on 12/20 pairs and loses none; always_verify gains on 13/19 assessed pairs and loses none.
- Under helper corruption, always_verify uses 4 model calls/run versus 8 for full_restart. Observed mean latency is 2752.3 ms versus 4856.2 ms. This is descriptive evidence from one repetition per case, not proof of stable speedup.
- Under QA corruption, unprotected and full_restart continue without triggering policy recovery. Their eventual answers must not be described as successful restart recovery.
- Clean controls also have answer-quality problems. Fault-case differences cannot all be attributed to recovery.
- Review candidates include unsupported refund timing/destinations, incorrect amounts and claims of completed repair where the record supports only an intervention plus retest.

## Exact remaining evaluation gaps

| Slot | Event | Why no valid draft assessment exists |
|---|---|---|
| BASE-0027__NONE__always_verify__r1 | bf263e2c-fab8-41f6-a310-b62f87f43207:49 | Non-exact answer quotation after the configured retries |
| BASE-0007__HELPER_CORRUPTION__always_verify__r1 | 4f7ef584-a85a-4845-8d5b-5316332da5a9:62 | Nonexistent source-evidence pointer after the configured retries |

Review these two drafts directly. They are evaluation gaps, not failed experimental executions. No additional paid calls or original experiment reruns are needed to inspect their saved evidence.

## Review and interpretation limits

All human fields remain **UNREVIEWED**. The judge shares the original answer-generation model, so independent human review is particularly important. Nine combined DATA_ISSUE labels occur under injected helper corruption: check whether the judge confused corrupted observations with a genuinely misaligned authoritative environment. They are not confirmed dataset defects.

Twenty-four overall labels were derived locally from unchanged LLM criterion assessments using the repository's existing aggregation rule. Every associated quote and source value still passed the unchanged strict validator. Original model labels and response files are preserved in local_aggregation_audit.json and responses/.

Read [RESULTS.md](RESULTS.md), then [priority_review_with_context.csv](priority_review_with_context.csv). Compare the question, authoritative record, observed record and answer before filling the five human criteria, reviewer, timestamp and rationale. The [complete review table](complete_review_with_context.csv) contains all 811 items. Non-priority rows are not automatically approved. The follow-up queue includes a reproducible sample of 60 otherwise eligible PASS items.

See [PHASE1_LLM_ADDENDUM.md](PHASE1_LLM_ADDENDUM.md) for the requirements update. The official course rubric/submission format remains unconfirmed because no official course document was found in the audited repository.

## Validation and publication scope

Thirty offline unit tests passed, plus a 12-request simulated concurrency check. All 2,456 raw experiment files and 2,461 frozen source/review inputs retain their recorded hashes. Credential scanning found no configured API key in this package.

This delivery adds only this English analysis directory. Original results, frozen experiment settings and prior reviews are unchanged. The base audited commit is `2b63ab7b0bc9b3eff6ba7a6be4f5961d8a8bc456` on the history of `Billing_loop_structure`. Historical validation fields such as `no_commit_or_push: true` describe the completed analysis stage, before the user's subsequent authorization to publish this package. Publication uses a normal fast-forward push; no force push or forced merge is intended.
