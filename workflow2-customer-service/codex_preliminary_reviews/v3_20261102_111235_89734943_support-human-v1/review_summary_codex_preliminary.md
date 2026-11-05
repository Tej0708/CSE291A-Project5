# Codex preliminary v3 review — NOT HUMAN-VALIDATED

Source run: `/Users/yanghede/Downloads/CSE291A-Project5/results/helper_scope_v3_full/clean_audit_20261102_111235_89734943`. Rubric: **support-human-v1**, copied unchanged from the existing review tool. This independent review covers every saved helper answer; no historical human scores were used as labels. No workflow run, provider API call, source/data modification or human-review write was performed.

## Identity and coverage

Verified exact manifest/results/trace coverage of BASE-0001-NONE through BASE-0040-NONE: 40 distinct intended clean cases, 40 completed results, 40 matching terminal trace reports and 60 helper attempts. Every trace input has fault_type=none and fault_config=null and matches the primary dataset. All 60 observed records match saved clean references and actual helper prompt records; every original request and assigned issue was checked. All 11 manifest code hashes, dataset hash and fixture hash match current files. The run uses api-glm-5.3-flash, temperature 0; its llm.py hash is ffd8daee24856ebdaaed4d5b2174007c0317bea85d75badb37b9497dd4903abf. Earlier v2 and targeted v3 runs are excluded. The clean reference shares the authored fixture source and is not independent real-world verification. All available support documents were generic category instructions and added no refund time or destination.

## Preliminary results

| Level / criterion | PASS | FAIL | UNCERTAIN | Denominator |
|---|---:|---:|---:|---:|
| record_alignment | 60 | 0 | 0 | 60 |
| relevance | 60 | 0 | 0 | 60 |
| grounding | 52 | 8 | 0 | 60 |
| coverage | 60 | 0 | 0 | 60 |
| status_responsibility | 60 | 0 | 0 | 60 |
| Helper answer (four answer criteria) | 52 | 8 | 0 | 60 |
| Case (all expected issues and latest outputs) | 32 | 8 | 0 | 40 |

Preliminary helper pass fraction: **52/60 = 86.67%**. Preliminary case pass fraction: **32/40 = 80%**. No UNREVIEWED or DATA_ISSUE cases remain in this Codex assessment; none of these is a human-validated score. The five criteria are scored independently: unsupported refund details fail grounding without automatically failing relevance, coverage, or responsibility. Aggregation uses the existing review_app.summarize function read-only: record-alignment FAIL produces DATA_ISSUE, missing helpers fail, UNCERTAIN remains explicit, and all latest answer criteria must pass. There is one attempt per issue here.

Structural passes **40/40**, QA raw valid labels **20/20**, fallback **0/20** are separate diagnostics, not evidence for the semantic judgments. No new-ticket requirement, exclusion from the overall request, invented coordination status or whole-case completion claim was found in this run. This observation does not establish general fix success.

## All FAIL / UNCERTAIN items for human adjudication

Eight FAIL items, all grounding; zero UNCERTAIN items. Every other criterion on these helpers is PASS. The quoted claims below are not supported by the observed record, saved clean reference or generic policy. Exact source trace files are named by case ID under the selected run; iteration and issue identify the attempt.

### BASE-0003-NONE / duplicate_charge / iteration 1

**grounding: FAIL**

> Please allow your bank's standard processing time for it to appear on your statement.

The observed record and clean reference establish the refund and amount/currency, but provide no bank-processing or statement-posting guidance and no destination. Although no numerical deadline is given, instructing the user to wait the bank's standard processing time adds an unsupported refund-processing assumption. This is distinct from simply asking the user to report a missing refund.

Observed record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0003:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`. Clean reference has the same record.

### BASE-0007-NONE / charge_after_cancellation / iteration 1

**grounding: FAIL**

> Please allow your bank's standard processing time for it to appear on your statement.

The observed record and clean reference establish the refund and amount/currency, but provide no bank-processing or statement-posting guidance and no destination. Although no numerical deadline is given, instructing the user to wait the bank's standard processing time adds an unsupported refund-processing assumption. This is distinct from simply asking the user to report a missing refund.

Observed record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0007:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`. Clean reference has the same record.

### BASE-0010-NONE / duplicate_charge / iteration 1

**grounding: FAIL**

> The refund may take a few business days to appear on your bank statement depending on your bank.

The observed record and clean reference establish a USD 49 refund/reversal but contain no posting timeline. The hedged few-days estimate is still an unsupported material refund-timing claim; the generic billing policy supplies none.

Observed record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0010:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`. Clean reference has the same record.

### BASE-0011-NONE / duplicate_charge / iteration 1

**grounding: FAIL**

> Depending on your payment provider, it may take a few days to appear on your statement.

The observed record and clean reference establish a USD 49 refund/reversal but contain no posting timeline. The hedged few-days estimate is still an unsupported material refund-timing claim; the generic billing policy supplies none.

Observed record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0011:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`. Clean reference has the same record.

### BASE-0014-NONE / charge_after_cancellation / iteration 1

**grounding: FAIL**

> Please allow your bank's standard processing time for the refund to appear on your statement.

The observed record and clean reference establish the refund and amount/currency, but provide no bank-processing or statement-posting guidance and no destination. Although no numerical deadline is given, instructing the user to wait the bank's standard processing time adds an unsupported refund-processing assumption. This is distinct from simply asking the user to report a missing refund.

Observed record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0014:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`. Clean reference has the same record.

### BASE-0020-NONE / charge_after_cancellation / iteration 2

**grounding: FAIL**

> Please allow your bank's standard processing time for it to appear on your statement.

The observed record and clean reference establish the refund and amount/currency, but provide no bank-processing or statement-posting guidance and no destination. Although no numerical deadline is given, instructing the user to wait the bank's standard processing time adds an unsupported refund-processing assumption. This is distinct from simply asking the user to report a missing refund.

Observed record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0020:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`. Clean reference has the same record.

### BASE-0027-NONE / duplicate_charge / iteration 1

**grounding: FAIL**

> a refund of $49.00 USD has been issued to your original payment method. Depending on your bank, please allow a few business days for it to appear on your statement.

The observed record and clean reference establish a USD 49 reversal/refund, but neither specifies the original payment method as destination nor a few-business-days posting time. The request mentions a bank statement; that does not establish refund destination or processing duration.

Observed record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0027:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`. Clean reference has the same record.

### BASE-0031-NONE / duplicate_charge / iteration 1

**grounding: FAIL**

> a refund of $49.00 USD has been issued to your original payment method.

The observed record and clean reference establish a USD 49 refund/reversal but specify no payment destination. "Original payment method" is an unsupported destination claim. The scope sentence itself is legitimate and is not the failure.

Observed record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0031:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`. Clean reference has the same record.

## Interpretation notes for human calibration

- BASE-0031 duplicate_charge: “this addresses only the duplicate charge” is a legitimate helper scope statement. It passes status_responsibility; “original payment method” fails grounding.
- BASE-0003/0007/0014/0020: “standard processing time” supplies no numeric deadline, but still introduces bank-posting assumptions absent from the evidence. These four are explicitly queued for human adjudication; this review does not add a numeric-timeline-only exception to the rubric.
- BASE-0006/0036/0040: generic “check your payment account” does not assert a specific destination or time and passes. BASE-0039 issuer follow-up is conditional and based on an explicit card-settlement record.
- BASE-0008 password_reset: a conditional offer to reissue the link is consistent with the recorded reissuance action; it is not a claim that a future action has already occurred or a guarantee of repair.
- BASE-0007/0023/0028/0031 login: prospective “should resolve/address” with retry/failure follow-up does not assert observed repair.
- BASE-0027 installation: no supported OS version is provided, but the answer directs the user to requirements and a supported OS, then retries; no concrete platform/version is invented.
- BASE-0034: processor settlement is distinguished from unconfirmed statement posting; SIM-REF-0034 and issuer tracing are present. Honest uncertainty in the source is not reviewer UNCERTAIN.
- Refund amounts/currencies are supported synthetic ledger facts even when absent from the customer request. No extra requirement was imposed to answer another helper's issue or repeat every tool field.

## Reproducible PASS-case sample

Seed **20261102**, stratified sampling without replacement from preliminary PASS cases only. Sorted populations and selected IDs are recorded in pass_sample_manifest.json. Groups are sampled in fixed order tech_only, billing_only, multi_issue, with ceil(20% of each group) using one Python random.Random(seed). Sample **7/32 = 21.875%** of PASS cases; every helper in selected cases is included in pass_sample_helpers.csv. This covers single-issue technical, single-issue billing and multi-issue cases, with both helper types. It is a human-validation queue, not a representative accuracy estimate of all 40 cases.

- tech_only: 2/10: BASE-0005-NONE, BASE-0037-NONE.
- billing_only: 2/8: BASE-0030-NONE, BASE-0034-NONE.
- multi_issue: 3/14: BASE-0008-NONE, BASE-0012-NONE, BASE-0035-NONE.

Use reproduce_pass_sample.py to reproduce the exact selection without writing any files. Review all eight flagged billing answers plus every helper in the sampled PASS cases against the included evidence; retain independent human scores in the existing tool under the human reviewer identity. Do not import these preliminary scores as human approval.

All 300 criterion judgments, quoted answer/record evidence and rationales are in helper_assessments_codex_preliminary.csv and assessments_codex_preliminary.json; all 40 case verdicts are in case_assessments_codex_preliminary.csv. Source hashes and the unchanged rubric snapshot are included for reproducibility.
