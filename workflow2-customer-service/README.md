# Workflow 2 — current progress and team handoff

Updated 2026-11-02. **Formal QA-corruption experiment preparation is complete; the formal experiment has NOT been run.** Restart and always-verify are not implemented. Preparation used offline scripted fixtures only, with no model/provider calls.

## Current progress

- Completed the helper-scope fix and v3 clean baseline; preserved historical datasets, prompts, raw traces and assessment revisions.
- Completed the bounded live pilot: eight completed runs, three activated mixed-issue fault cases and one non-activation control. Activation caused repeated work followed by continuation to unresolved work; this is not full-restart recovery.
- Recorded the final pilot review and frozen evaluation rules. Latest-answer quality is 4 PASS / 4 FAIL runs; all 17 drafts contain 9 PASS / 8 FAIL. These judgments include preliminary Codex assessments and two scoped user adjudications, not blanket human sign-off.
- Added a separate formal observer with invocation-time stage/iteration, symmetric clean/fault Router receipt/action records, linked run/event/call IDs and complete nullable provider usage.
- Verified 20 mixed technical/billing cases from the dataset and froze **40 runs**: one clean + one `qa_first_missing_once_v1` per case, 10 clean-first / 10 fault-first, seed `20261102`, original budgets and pilot model/settings.
- Offline validation passed **31 workflow tests + 9 review-tool tests**, including 160 plain/observed fixture comparisons. Preparation verified 374 pre-existing files unchanged; this handoff subsequently updates documentation only.

## Where teammates should align logging schema and metrics

**Start with [TEAM_HANDOFF.md](TEAM_HANDOFF.md).** It maps each contract to its schema, implementation and tests, and distinguishes raw observations from derived metrics.

| Need | Files to read |
| --- | --- |
| Logging event fields, IDs, stage/iteration, dependencies | [event.schema.json](formal_experiment/event.schema.json), [formal_observer.py](formal_observer.py) |
| Raw per-run results, calls, usage, drafts and injection evidence | [result.schema.json](formal_experiment/result.schema.json), [formal_observer.py](formal_observer.py) |
| Activation, repeated work, affected stages, overhead and paired deltas | [metrics.schema.json](formal_experiment/metrics.schema.json), [paired_result.schema.json](formal_experiment/paired_result.schema.json), `evaluate()` in [run_formal_experiment.py](run_formal_experiment.py) |
| Answer-quality definitions and review fields | [BASELINE_EVALUATION_RULES.md](BASELINE_EVALUATION_RULES.md), [draft_assessment.schema.json](formal_experiment/draft_assessment.schema.json), [latest_answer_quality.schema.json](formal_experiment/latest_answer_quality.schema.json) |
| Frozen cases, schedule and settings | [manifest.json](formal_experiment/manifest.json) |
| Protocol, reproducible commands and remaining Phase 1 checklist | [PLAN.md](formal_experiment/PLAN.md) |
| Test evidence and preservation | [Preparation report](formal_experiment/REPORT.md), [workflow tests](formal_experiment/tests.txt), [review-tool tests](formal_experiment/review_tests_with_loopback.txt) |
| Final pilot findings and judgment provenance | [Final pilot report](results/workflow2_step3_pilot_local_20261102_120737/evaluation_user_adjudicated/REPORT.md) |

## Next direction

1. Align teammates on the logging and metric contracts linked above. Keep ledger completion, latest-per-issue answer quality and all-draft quality separate.
2. Verify the frozen manifest and obtain explicit authorization before live execution. Do not change prompts/settings or add defenses inside this frozen experiment.
3. Execute the 40-run schedule serially with fresh state per run. Keep skipped/ineligible/error/not-attempted slots; no replacement or outcome-dependent reruns.
4. Inspect activation and Router-consumption evidence, perform offline review of every draft under the frozen rules, then publish paired overhead and separate quality results with explicit denominators.
5. Consider restart and always-verify only as a later, separately specified implementation/evaluation phase with matching baselines.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_formal_experiment.py verify
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s human_review_tool -p 'test_*.py' -v
```

The review-tool HTTP test needs local loopback permission. Future execution and offline evaluation commands are in [PLAN.md](formal_experiment/PLAN.md); they are not instructions to run the experiment now.

---

The earlier v2 progress record below is retained for context. Its pending-work statements describe that milestone, not the current state above.

# Historical progress: v2 baseline

## Status at the v2 milestone

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

### v2 validation at that milestone

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


## Next steps recorded at the v2 milestone (superseded above)

1. Review the latest v2 answers and confirm the run used the intended code and fixture versions.
2. Finalize and document the task-success scoring criteria.
3. Freeze the dataset, fixtures, code, and model configuration.
4. Verify fault activation and downstream consumption before batch experiments.
5. Measure fault propagation, affected stages, task success, extra calls/tokens, and latency.
6. Implement and evaluate full restart and an always-verify comparison.

