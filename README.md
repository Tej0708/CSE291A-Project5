# Workflow 2 Progress Update

## Current Status

The customer-support workflow runs locally with both rule-based and LLM backends:

Router → Billing / Technical Helper → QA → Router

We have completed dataset cleanup, clean-baseline logging, QA label validation, and scenario-specific mock tool records. The latest v2 clean run has finished locally. Full answer review is pending.

Formal fault-injection measurements, full-restart recovery, and the always-verify comparison are not yet complete.

## Completed Work

### 1. Dataset Review and Cleanup

- Reviewed the 40 original base requests and their expected issue labels.
- Rewrote duplicate request texts to produce 40 distinct request strings.
- Kept each request consistent across its five experimental variants.
- Reclassified the former `ambiguous` cases as `multi_issue`, since they explicitly describe multiple issues.
- Current dataset: `support_cases_unique40.jsonl`.
- The file contains 200 records: 40 base requests × 5 conditions.

Distinct wording does not imply 40 distinct problem types. Some requests intentionally share issue categories.

### 2. Clean-Baseline Audit Logging

Added `run_clean_audit.py` to record:

- Actual issue labels and routing.
- Model prompts, responses, model name, and token usage.
- Helper answers and tool records.
- QA feedback and fallback decisions.
- Workflow and model-call durations.
- Source-code and dataset hashes.
- Structural checks and an answer-review CSV.

Structural checks and answer correctness are evaluated separately. A `resolved` status does not automatically establish task success.

### 3. QA Label Fix

Previously, an invalid model label could be replaced by a valid label while its incorrect explanation remained unchanged.

Updated `csa_workflow/llm.py` and `csa_workflow/agents.py` to:

- Give QA both resolved and unresolved issue lists.
- Validate the model response shape and selected label.
- Fall back to the first unresolved issue when necessary.
- Generate the effective explanation from workflow state.
- Preserve the raw model output and `fallback_used` in logs.

Validation occurs before the QA fault-injection hook, so controlled QA corruption remains possible.

### 4. Scenario-Specific Mock Tools — v2

Reviewing the earlier baseline exposed mismatches between detailed requests and generic tool records. For example, a PDF-upload crash received a Settings-crash solution.

Added `csa_workflow/scenario_records.json` with:

- 40 synthetic scenarios.
- 60 issue-specific records.
- Matching initial records shared by clean and fault variants.
- Explicit facts for subscription plans, installation errors, crash contexts, and billing outcomes.

Updated the workflow so that:

- Tools select records using the base case ID and assigned issue.
- Request text is checked against its scenario.
- Helpers receive the original user request.
- Unsupported issues return `unavailable` instead of an unrelated generic record.
- Helper prompts request concise, evidence-grounded answers.
- Audit logs use scenario-specific reference records and include the fixture hash.

These records are preauthored simulated environment facts, not real transactions or verified product fixes.

## Validation Results

### Earlier Development Baseline: QA Fix + Generic Tools

- 40/40 runs completed without runtime errors.
- 40/40 structural checks passed.
- 20 QA model selections were valid; no fallback was needed.
- 120 LLM calls and 22,142 reported tokens.
- Total workflow time: approximately 106.95 seconds.

Answer review nevertheless found unsupported claims and scenario/tool mismatches. These results are retained as development results, not final end-to-end success evidence.

### Current v2

- 17 offline regression tests passed.
- Scripted-model tests covered all 40 clean requests.
- Fixture checks covered all 200 variants.
- Targeted tests confirmed that the four existing fault hooks remain observable.
- The live BASE-0022 sample passed answer review: it correctly identified the annual plan and explained the corrected account display.
- The full 40-case LLM run has completed locally; aggregate results and answer correctness still require review.

Offline scripted tests are not evidence of live-model accuracy.

## Known Limitations

- Helper prompts reduce unsupported claims but do not guarantee factual correctness.
- QA does not yet perform semantic verification of helper answers.
- Internal evidence acceptance can still admit corrupted records.
- Technical completion means providing applicable, evidence-backed remediation; successful user-side repair is not observed.
- The rule classifier still overclassifies `subscription_status` in five cases.
- In v2, those extra issues remain unresolved because no matching scenario record exists.
- Existing fault configurations still need activation checks. An untriggered or ignored fault is not evidence of robustness.
- The audit reference uses the same fixture service; semantic correctness still requires independent review.


## Next Steps

1. Review the latest v2 answers and confirm the run used the intended code and fixture versions.
2. Finalize and document the task-success scoring criteria.
3. Freeze the dataset, fixtures, code, and model configuration.
4. Verify fault activation and downstream consumption before batch experiments.
5. Measure fault propagation, affected stages, task success, extra calls/tokens, and latency.
6. Implement and evaluate full restart and an always-verify comparison.

