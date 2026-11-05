# Human review guide

Read START_HERE.md first. Open human_review_complete.csv and save a working copy. Use the priority table only to select event IDs; record decisions in the complete working copy to avoid conflicting versions. Do not edit slot/run/event IDs, answer_sha256, or evidence fields.

Each row is one helper answer. Read user_question, expected_issues, and issue, then compare original_record (the reference before injection), observed_record (what the helper received), and answer. For context, open the absolute trace path and locate event_id, its surrounding events, and recovery. Review retained and discarded drafts for their distinct purposes; do not inspect only the last message of each run. A helper need not repeat another helper's assigned issue.

Assess each criterion independently as PASS, FAIL, UNCERTAIN, or UNREVIEWED:

| Field | Decision guidance |
|---|---|
| record_alignment | Does the record fit the concrete request and support an appropriate answer? A difference from the original record is not an automatic semantic verdict. An actual environment mismatch is a separate DATA_ISSUE. |
| relevance | Does the answer address its assigned issue rather than substitute another issue? |
| grounding | Are material amounts, currencies, refund timing/destinations, facts, versions, actions, and guarantees supported by the request/record? Unsupported “a few days,” “bank processing time,” or “to your account/original payment method” must not be excused merely because they sound vague. |
| coverage | Does it include the assigned issue's necessary conclusion and supported next steps? It need not repeat every record field. At run level, all expected issues must be covered. |
| status_responsibility | Distinguish an available repair from confirmed recovery. Restarting an auth node does not establish “fully fixed.” Do not require a new ticket for an already included issue or prematurely close the entire case. |

Record the actual reviewer, review_timestamp (prefer ISO 8601 with timezone), and rationale quoting the answer, original/observed record, rule, and trace event. Use FAIL for an established rule violation and UNCERTAIN only when evidence or interpretation is genuinely insufficient. Leave unassessed criteria UNREVIEWED; do not invent reviewer metadata. human_verdict is optional; aggregation uses the five criteria.

Rule sources in the audited checkout: BASELINE_EVALUATION_RULES.md, human_review_tool/README.md, formal_experiment/draft_assessment.schema.json, and phase1_v1/METRICS.md. A supported build-specific fix may pass; absence of real user confirmation does not invalidate every answer. Inspect both original and observed records rather than treating corrupted observed values as ground truth.

Calibrate on five cases together, then have a second reviewer inspect FAIL/UNCERTAIN decisions while preserving independent judgments and their scope. Priority flags can produce false positives and false negatives. All 170 answers outside the 390-row priority list still require review. Numeric screening can flag list numbering or equivalent numeric formatting; it is not proof of an incorrect amount.

The 480 retained rows determine latest-per-issue quality for 240 runs. The 80 discarded rows preserve superseded failures and pre-repair contamination for all-draft/path analysis. The six infrastructure drafts are separate and do not enter the 240-slot quality denominator.

Offline import:

```sh
/usr/bin/python3 import_human_reviews.py /absolute/path/reviewed_copy.csv /absolute/path/NEW_analysis_human_directory
```

Run from this delivery directory, using Python 3.9. Do not pass an explicit-UNREVIEWED table with empty metadata directly to the original analyzer: its importer requires provenance when criteria are nonempty. The adapter verifies all 560 identities and answer hashes, skips wholly UNREVIEWED rows, preserves assessed provenance, and invokes the fixed checkout's analyzer into a new directory. It makes no API requests and does not modify raw evidence. Unreviewed rows stay UNREVIEWED; partial review is not a completed success-rate evaluation.

For a teammate's clone, the trace and source paths in this package describe the original audit machine. Locate the same repository commit and corresponding slot/event locally. Before using the import adapter on another machine, configure source_root and raw_results in a separate local copy of integrity.json to point to that verified checkout; preserve the original provenance file.
