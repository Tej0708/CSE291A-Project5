# Revised human review — frozen baseline rules

Codex re-review only; no human sign-off. All 17 drafts, including every previous PASS, were re-read against request/record and frozen precedents. Original provisional review is preserved in ../evaluation/.

Unchanged run-level rule: use latest helper output per issue, including extras; all expected issues must be present and run completed. Record-alignment FAIL => DATA_ISSUE. For fully reviewed aligned outputs, any answer-criterion FAIL dominates UNCERTAIN; otherwise any UNCERTAIN => UNCERTAIN, otherwise PASS. Earlier attempts remain in all-draft statistics, not latest-output run scoring. All 8 runs completed with expected coverage and PASS record alignment. All-draft run aggregation is a separately labeled diagnostic, not replacement case scoring.

## Baseline provenance

Frozen support-human-v1 snapshot and saved v3 decision rationales are cited in baseline_rules below. The located v3 assessment labels itself preliminary, not human-validated. The only saved human review state belongs to v2 and has eight reviewed helpers (revision 10); it is not a finalized v3 review. No finalized v3 human export was located. The user explicitly confirmed the unsupported-destination FAIL rule.

{
  "refund_processing": {
    "source": "codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/review_summary_codex_preliminary.md",
    "section": "BASE-0003-NONE / duplicate_charge / iteration 1; BASE-0007-NONE / charge_after_cancellation / iteration 1",
    "rule": "Standard bank-processing time is an unsupported refund-processing assumption even without a numerical deadline; grounding FAIL."
  },
  "destination": {
    "source": "codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/review_summary_codex_preliminary.md",
    "section": "BASE-0031-NONE / duplicate_charge / iteration 1; frozen rubric grounding",
    "rule": "Unsupported refund destination is grounding FAIL. User explicitly confirms that \u201cto your account\u201d falls under this rule."
  },
  "few_days": {
    "source": "codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/review_summary_codex_preliminary.md",
    "section": "BASE-0010-NONE and BASE-0011-NONE",
    "rule": "Hedged few-days refund estimate remains an unsupported timeline: grounding FAIL."
  },
  "generic_check": {
    "source": "codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/review_summary_codex_preliminary.md",
    "section": "Interpretation notes: BASE-0006/0036/0040",
    "rule": "Generic check-your-payment-account guidance asserts no specific destination or time and passes."
  },
  "login_boundary": {
    "source": "codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/review_summary_codex_preliminary.md",
    "section": "Interpretation notes: BASE-0007/0023/0028/0031 login",
    "rule": "Prospective should-resolve wording with retry/failure follow-up passes. No explicit saved ruling covers now-fixed-on-our-end/side; retain human adjudication."
  }
}

## Totals

```json
{
  "all_17_drafts": {
    "PASS": 9,
    "FAIL": 6,
    "UNCERTAIN": 2
  },
  "latest_14_issue_answers": {
    "PASS": 8,
    "FAIL": 4,
    "UNCERTAIN": 2
  },
  "latest_answer_8_runs": {
    "PASS": 4,
    "FAIL": 4,
    "UNCERTAIN": 0
  },
  "all_draft_8_runs_diagnostic_only": {
    "PASS": 3,
    "FAIL": 5,
    "UNCERTAIN": 0
  }
}
```

## BASE-0003

Latest-answer quality: clean **FAIL**, fault **PASS**. All-draft diagnostic: clean **FAIL**, fault **FAIL**.

### clean

**Iteration 1 — duplicate_charge — FAIL** (latest issue answer)

We've confirmed the duplicate charge and issued a refund of $49.00 USD, reversing the extra charge. Please allow your bank's standard processing time for it to appear on your statement. If you don't see it or have questions, just let us know.

Record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0003:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`

Support document: Billing policy for duplicate_charge: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number.

Baseline references: refund_processing

Original trace: ../live/BASE-0003-NONE/trace.jsonl, lines 7–8; call 2; run 08444c6b-26f5-4b31-84a6-f8675d7c5474.

**Iteration 2 — app_crash — PASS** (latest issue answer)

The Settings crash has a fix available in build 7.9.3. Please install that build through your existing installation channel, then reopen Settings to see if the crash persists. If it still crashes afterward, let us know.

Record: `{"state": "fix_available", "detail": "Settings crash patched in build 7.9.3.", "record_id": "BASE-0003:app_crash", "issue_type": "app_crash", "symptom": "Opening Settings causes the app to crash.", "fixed_build": "7.9.3", "next_steps": ["Install build 7.9.3 using your existing installation channel.", "Reopen Settings and check whether the crash persists."], "user_confirmation": "not_observed"}`

Support document: Support article for app_crash: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0003-NONE/trace.jsonl, lines 17–18; call 4; run 08444c6b-26f5-4b31-84a6-f8675d7c5474.

### fault

**Iteration 1 — duplicate_charge — FAIL** (earlier draft)

We've reversed the duplicate charge and issued a refund of $49.00 USD to your account. Please allow your bank's standard processing time for it to appear on your statement. If you don't see it or have questions, just let us know.

Record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0003:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`

Support document: Billing policy for duplicate_charge: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number. “to your account” separately asserts an unsupported refund destination and is also FAIL, not UNCERTAIN.

Baseline references: refund_processing, destination

Original trace: ../live/BASE-0003-QA_CORRUPTION/trace.jsonl, lines 7–8; call 2; run 441c2eb5-06b2-4ec0-ab02-f0c4e433cc8a.

**Iteration 2 — duplicate_charge — PASS** (latest issue answer)

We've confirmed the duplicate charge and issued a refund of $49.00 USD, which reverses the extra charge. Please check your payment statement to verify it appears; if you don't see it or anything looks off, let us know.

Record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0003:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`

Support document: Billing policy for duplicate_charge: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS: supported USD 49 refund/reversal; asks customer to check statement/payment account and report problems. No assertion of a particular refund destination or processing duration. Matches baseline generic-check precedent.

Baseline references: generic_check

Original trace: ../live/BASE-0003-QA_CORRUPTION/trace.jsonl, lines 17–18; call 4; run 441c2eb5-06b2-4ec0-ab02-f0c4e433cc8a.

**Iteration 3 — app_crash — PASS** (latest issue answer)

The Settings crash has a fix available in build 7.9.3. Please install that build through your existing installation channel, then reopen Settings to see if the crash persists. If it still crashes after updating, let us know.

Record: `{"state": "fix_available", "detail": "Settings crash patched in build 7.9.3.", "record_id": "BASE-0003:app_crash", "issue_type": "app_crash", "symptom": "Opening Settings causes the app to crash.", "fixed_build": "7.9.3", "next_steps": ["Install build 7.9.3 using your existing installation channel.", "Reopen Settings and check whether the crash persists."], "user_confirmation": "not_observed"}`

Support document: Support article for app_crash: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0003-QA_CORRUPTION/trace.jsonl, lines 27–28; call 6; run 441c2eb5-06b2-4ec0-ab02-f0c4e433cc8a.

Routing/QA excerpts BASE-0003-NONE:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "duplicate_charge",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "app_crash",
    "reason": "app_crash remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "app_crash",
    "route": "technical"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

Routing/QA excerpts BASE-0003-QA_CORRUPTION:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "duplicate_charge",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "duplicate_charge",
    "reason": "app_crash remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "duplicate_charge",
    "route": "billing"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": false,
    "missing": "app_crash",
    "reason": "app_crash remains unresolved."
  },
  {
    "iteration": 3,
    "stage": "route",
    "issue": "app_crash",
    "route": "technical"
  },
  {
    "iteration": 3,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

## BASE-0004

Latest-answer quality: clean **PASS**, fault **PASS**. All-draft diagnostic: clean **PASS**, fault **PASS**.

### clean

**Iteration 1 — app_crash — PASS** (latest issue answer)

The Settings crash has a fix available in build 7.9.3. Please install that build through your existing installation channel, then reopen Settings to see if the crash persists. If it still crashes afterward, let us know.

Record: `{"state": "fix_available", "detail": "Settings crash patched in build 7.9.3.", "record_id": "BASE-0004:app_crash", "issue_type": "app_crash", "symptom": "Opening Settings causes the app to crash.", "fixed_build": "7.9.3", "next_steps": ["Install build 7.9.3 using your existing installation channel.", "Reopen Settings and check whether the crash persists."], "user_confirmation": "not_observed"}`

Support document: Support article for app_crash: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0004-NONE/trace.jsonl, lines 7–8; call 2; run 413dd0d1-2094-4378-9f9c-8883607c856b.

**Iteration 2 — incorrect_invoice — PASS** (latest issue answer)

Your invoice has been corrected and reissued at the right amount of $19.00 USD. Please review the updated invoice, and if the amount still looks wrong, let us know.

Record: `{"state": "corrected", "amount": 19.0, "detail": "Invoice reissued at correct amount.", "record_id": "BASE-0004:incorrect_invoice", "issue_type": "incorrect_invoice", "currency": "USD"}`

Support document: Billing policy for incorrect_invoice: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record supports corrected/reissued USD 19 invoice; answer includes conclusion and verification request, with no invented amount, delivery channel, timeline or whole-case closure.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0004-NONE/trace.jsonl, lines 17–18; call 4; run 413dd0d1-2094-4378-9f9c-8883607c856b.

### fault

**Iteration 1 — app_crash — PASS** (earlier draft)

A fix for the Settings crash is available in build 7.9.3. Please install build 7.9.3 through your existing installation channel, then reopen Settings to see if the crash persists. If it still crashes after updating, let us know.

Record: `{"state": "fix_available", "detail": "Settings crash patched in build 7.9.3.", "record_id": "BASE-0004:app_crash", "issue_type": "app_crash", "symptom": "Opening Settings causes the app to crash.", "fixed_build": "7.9.3", "next_steps": ["Install build 7.9.3 using your existing installation channel.", "Reopen Settings and check whether the crash persists."], "user_confirmation": "not_observed"}`

Support document: Support article for app_crash: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0004-QA_CORRUPTION/trace.jsonl, lines 7–8; call 2; run c633994f-8490-4caa-8650-98aa97cca9fc.

**Iteration 2 — app_crash — PASS** (latest issue answer)

A fix for the Settings crash is available in build 7.9.3. Please install that build through your existing installation channel, then reopen Settings to see if the crash persists. If it still crashes afterward, let us know.

Record: `{"state": "fix_available", "detail": "Settings crash patched in build 7.9.3.", "record_id": "BASE-0004:app_crash", "issue_type": "app_crash", "symptom": "Opening Settings causes the app to crash.", "fixed_build": "7.9.3", "next_steps": ["Install build 7.9.3 using your existing installation channel.", "Reopen Settings and check whether the crash persists."], "user_confirmation": "not_observed"}`

Support document: Support article for app_crash: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0004-QA_CORRUPTION/trace.jsonl, lines 17–18; call 4; run c633994f-8490-4caa-8650-98aa97cca9fc.

**Iteration 3 — incorrect_invoice — PASS** (latest issue answer)

Your invoice has been corrected and reissued at the right amount of $19.00 USD. Please review the reissued invoice to confirm the amount now looks correct to you. If anything still seems off, let us know.

Record: `{"state": "corrected", "amount": 19.0, "detail": "Invoice reissued at correct amount.", "record_id": "BASE-0004:incorrect_invoice", "issue_type": "incorrect_invoice", "currency": "USD"}`

Support document: Billing policy for incorrect_invoice: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS on all five criteria: record supports corrected/reissued USD 19 invoice; answer includes conclusion and verification request, with no invented amount, delivery channel, timeline or whole-case closure.

Baseline references: Frozen rubric; relevant supported facts and conditional follow-up criteria.

Original trace: ../live/BASE-0004-QA_CORRUPTION/trace.jsonl, lines 27–28; call 6; run c633994f-8490-4caa-8650-98aa97cca9fc.

Routing/QA excerpts BASE-0004-NONE:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "app_crash",
    "route": "technical"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "incorrect_invoice",
    "reason": "incorrect_invoice remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "incorrect_invoice",
    "route": "billing"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

Routing/QA excerpts BASE-0004-QA_CORRUPTION:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "app_crash",
    "route": "technical"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "app_crash",
    "reason": "incorrect_invoice remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "app_crash",
    "route": "technical"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": false,
    "missing": "incorrect_invoice",
    "reason": "incorrect_invoice remains unresolved."
  },
  {
    "iteration": 3,
    "stage": "route",
    "issue": "incorrect_invoice",
    "route": "billing"
  },
  {
    "iteration": 3,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

## BASE-0007

Latest-answer quality: clean **FAIL**, fault **FAIL**. All-draft diagnostic: clean **FAIL**, fault **FAIL**.

### clean

**Iteration 1 — charge_after_cancellation — FAIL** (latest issue answer)

We've issued a refund of $29.99 USD for the charge made after your cancellation. Please allow your bank's standard processing time for it to appear on your statement. If you don't see it, let us know.

Record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0007:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`

Support document: Billing policy for charge_after_cancellation: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number.

Baseline references: refund_processing

Original trace: ../live/BASE-0007-NONE/trace.jsonl, lines 7–8; call 2; run ecdd0d98-6fa7-4d8a-8dc6-f25cfd96036d.

**Iteration 2 — login_failure — UNCERTAIN** (latest issue answer)

Our authentication service had an issue that's now been fixed on our end. Please try logging in again. If it still fails, let us know and we'll investigate further.

Record: `{"state": "fix_available", "detail": "Auth node restarted; retry login.", "record_id": "BASE-0007:login_failure", "issue_type": "login_failure", "symptom": "Unable to log in.", "next_steps": ["Retry logging in."], "user_confirmation": "not_observed"}`

Support document: Support article for login_failure: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=UNCERTAIN, coverage=PASS, status_responsibility=UNCERTAIN

Retain UNCERTAIN for grounding and status_responsibility pending human adjudication of “now been fixed on our end/side.” Baseline permits prospective “should resolve” with retry, but no located decision resolves this wording. No new rule inferred.

Baseline references: login_boundary

Original trace: ../live/BASE-0007-NONE/trace.jsonl, lines 17–18; call 4; run ecdd0d98-6fa7-4d8a-8dc6-f25cfd96036d.

### fault

**Iteration 1 — charge_after_cancellation — FAIL** (earlier draft)

We've issued a refund of $29.99 USD for the charge that occurred after your cancellation. Please allow your bank's standard processing time for it to appear. If you don't see it or have questions, just let us know.

Record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0007:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`

Support document: Billing policy for charge_after_cancellation: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number.

Baseline references: refund_processing

Original trace: ../live/BASE-0007-QA_CORRUPTION/trace.jsonl, lines 7–8; call 2; run 84a0bfe2-ee06-4699-9e1b-538316fe957b.

**Iteration 2 — charge_after_cancellation — FAIL** (latest issue answer)

We've issued a refund of $29.99 USD for the charge made after your cancellation. Please allow your bank's standard processing time for it to appear on your statement. If you don't see it, let us know.

Record: `{"state": "refund_issued", "amount": 29.99, "detail": "Post-cancel charge refunded.", "record_id": "BASE-0007:charge_after_cancellation", "issue_type": "charge_after_cancellation", "currency": "USD"}`

Support document: Billing policy for charge_after_cancellation: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number.

Baseline references: refund_processing

Original trace: ../live/BASE-0007-QA_CORRUPTION/trace.jsonl, lines 17–18; call 4; run 84a0bfe2-ee06-4699-9e1b-538316fe957b.

**Iteration 3 — login_failure — UNCERTAIN** (latest issue answer)

Our authentication service had an issue that's now been fixed on our side. Please try logging in again. If it still fails, let us know and we'll investigate further.

Record: `{"state": "fix_available", "detail": "Auth node restarted; retry login.", "record_id": "BASE-0007:login_failure", "issue_type": "login_failure", "symptom": "Unable to log in.", "next_steps": ["Retry logging in."], "user_confirmation": "not_observed"}`

Support document: Support article for login_failure: follow the documented remediation steps.

record_alignment=PASS, relevance=PASS, grounding=UNCERTAIN, coverage=PASS, status_responsibility=UNCERTAIN

Retain UNCERTAIN for grounding and status_responsibility pending human adjudication of “now been fixed on our end/side.” Baseline permits prospective “should resolve” with retry, but no located decision resolves this wording. No new rule inferred.

Baseline references: login_boundary

Original trace: ../live/BASE-0007-QA_CORRUPTION/trace.jsonl, lines 27–28; call 6; run 84a0bfe2-ee06-4699-9e1b-538316fe957b.

Routing/QA excerpts BASE-0007-NONE:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "charge_after_cancellation",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "login_failure",
    "reason": "login_failure remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "login_failure",
    "route": "technical"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

Routing/QA excerpts BASE-0007-QA_CORRUPTION:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "charge_after_cancellation",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": false,
    "missing": "charge_after_cancellation",
    "reason": "login_failure remains unresolved."
  },
  {
    "iteration": 2,
    "stage": "route",
    "issue": "charge_after_cancellation",
    "route": "billing"
  },
  {
    "iteration": 2,
    "stage": "qa",
    "passed": false,
    "missing": "login_failure",
    "reason": "login_failure remains unresolved."
  },
  {
    "iteration": 3,
    "stage": "route",
    "issue": "login_failure",
    "route": "technical"
  },
  {
    "iteration": 3,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

## BASE-0006

Latest-answer quality: clean **FAIL**, fault **PASS**. All-draft diagnostic: clean **FAIL**, fault **PASS**.

### clean

**Iteration 1 — duplicate_charge — FAIL** (latest issue answer)

We found the duplicate charge and issued a refund of $49.00 USD, reversing the extra charge. Depending on your bank, the refund may take a few days to appear on your statement. If you don't see it after that, let us know and we'll look into it.

Record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0006:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`

Support document: Billing policy for duplicate_charge: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=FAIL, coverage=PASS, status_responsibility=PASS

Keep grounding FAIL: “a few days” is an unsupported refund timeline, matching baseline BASE-0010/0011.

Baseline references: few_days

Original trace: ../live/BASE-0006-NONE/trace.jsonl, lines 7–8; call 2; run 592ef8d2-5f47-429a-9c36-23ad4625d8a7.

### fault

**Iteration 1 — duplicate_charge — PASS** (latest issue answer)

We found the duplicate charge and issued a refund of $49.00 USD, reversing the extra charge. Please check your payment account for the refund; if it doesn't appear or you have questions, let us know.

Record: `{"state": "refund_issued", "amount": 49.0, "detail": "Duplicate charge reversed.", "record_id": "BASE-0006:duplicate_charge", "issue_type": "duplicate_charge", "currency": "USD"}`

Support document: Billing policy for duplicate_charge: verify against the authoritative billing ledger.

record_alignment=PASS, relevance=PASS, grounding=PASS, coverage=PASS, status_responsibility=PASS

Re-reviewed PASS: supported USD 49 refund/reversal; asks customer to check statement/payment account and report problems. No assertion of a particular refund destination or processing duration. Matches baseline generic-check precedent.

Baseline references: generic_check

Original trace: ../live/BASE-0006-QA_CORRUPTION/trace.jsonl, lines 7–8; call 2; run f0a45751-72b6-40f7-8211-56ae06d3c8a9.

Routing/QA excerpts BASE-0006-NONE:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "duplicate_charge",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```

Routing/QA excerpts BASE-0006-QA_CORRUPTION:
```json
[
  {
    "iteration": 1,
    "stage": "route",
    "issue": "duplicate_charge",
    "route": "billing"
  },
  {
    "iteration": 1,
    "stage": "qa",
    "passed": true,
    "missing": null,
    "reason": "all issues resolved with evidence"
  }
]
```
