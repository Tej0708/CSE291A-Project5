# Step 2: qa_first_missing_once_v1

Implemented and validated offline only. No paid API calls or recovery strategies. No live-model susceptibility, task-quality effects, or recovery success are claimed.

## Implementation and preservation

Opt in through `run_fault_audit.py --profile qa_first_missing_once_v1`, or supply a QA-corruption case with fault_config `{"profile":"qa_first_missing_once_v1","target_stage":"qa_to_router"}`. The audit CLI restricts this profile to QA cases and rejects combination with the legacy trigger override. It records original/effective configurations separately. Omitting the option preserves the existing experiment.

Changed files: `csa_workflow/faults.py` implements the profile; `csa_workflow/agents.py` passes real workflow state at the existing QA-output boundary for this profile; `run_fault_audit.py` selects the profile and records eligibility, propagation, routing and actions. New focused tests are in `test_qa_profile.py`. No other fault implementations changed.

The first eligible output must name a legal OPEN issue actually present in this execution's ledger, have a different legal RESOLVED issue in that ledger, and precede the last allowed Router iteration. The replacement is the most recently resolved issue, observed at QA boundaries after normal evidence checks; simultaneous resolutions use ascending lexical issue-label order. This workflow resolves issues only in QA, so these observations capture its resolution transitions. Eligibility never consults gold labels. Scripted classification remains explicit test scaffolding in the existing scripted backend.

Only missing_issue changes. passed and reason remain verbatim, even when the retained reason describes the original issue. The injector tracks one mutation per new case execution; later feedback is untouched. It does not replay, clear, repair, reorder, or synthesize workflow state.

`pre_step2_source.zip` preserves the pre-change source. `preservation_manifest.json` and `preservation_check.json` verify all pre-existing datasets, configurations, reviews, historical fault-audit artifacts and results remain byte-identical. Only the three listed implementation files changed. The existing no-op guard from the prior step is preserved. QA defenses, helper prompts and scoring are unchanged.

## Why the historical experiment activated 0/40

It requires iteration >= 2 and an exact configured original missing label. Single-issue cases normally finish at iteration 1; two-issue cases normally have no missing label by iteration 2. Normal processing order also handles the configured original label first. The rule classifier's five longer cases still do not match the original label at the required boundary. The hook was reached, but its mutation conditions were not met.

That historical experiment substitutes the route name `technical`, which is not a legal issue label, and can persistently replay its mutation. The new experiment uses a legal, already resolved issue from actual state, fires at the first eligible event, changes no other feedback field, and never artificially replays. Both experiments and their results are separately labeled and retained.

## Observed counts (cases)

| Experiment / backend | Total | Eligible | Mutated | Downstream consumed | Revisited resolved issue | Skipped |
|---|---:|---:|---:|---:|---:|---:|
| New profile / rule | 40 | 21 | 21 | 21 | 21 | 19 |
| New profile / scripted | 40 | 20 | 20 | 20 | 20 | 20 |
| Original / rule | 40 | 0 | 0 | 0 | 0 | 40 |
| Original / scripted | 40 | 0 | 0 | 0 | 0 | 40 |

New-profile skipped cases all have `no_missing_issue`: 19 rule, 20 scripted. Conditional activation/receipt is 21/21 eligible rule cases and 20/20 eligible scripted cases. Original eligibility is zero, so conditional activation has no applicable denominator. All original cases encounter `before_trigger_iteration`; 21 rule and 20 scripted cases additionally encounter `original_label_mismatch_or_no_missing_issue`. These per-case reason categories overlap.

All new-profile mutations occurred at QA iteration 1 and reached Router iteration 2. Each caused one actual helper revisit of the resolved replacement while another ledger issue remained open. All following QA calls were left untouched; their returned missing labels naturally reverted to unresolved issues. No persistent corruption loop was imposed or observed.

Example BASE-0003: QA's app_crash hint becomes duplicate_charge; Router selects duplicate_charge and calls the billing helper again; the next QA output names app_crash. The reversed-order focused test similarly substitutes app_crash for duplicate_charge and verifies actual Router receipt and helper execution.

Scripted cases: 20 single-issue cases finish in one iteration; 20 multi-issue cases finish in three. Rule cases: 19 finish in one iteration, 16 in three, and five exhaust the four-iteration budget with blocked status. Those five also exhaust the original-profile budget due to existing subscription_status overclassification. BASE-0014 is the additional eligible rule case: although gold labels specify one issue, the actual classifier ledger contains an extra unresolved subscription_status. The profile does not invent or remove that issue. These statuses describe workflow control only, not task quality or successful recovery.

## Validation and artifacts

26 root-suite tests passed, including nine new focused tests and unchanged-history comparisons against saved pre-Step-2 results for all 200 dataset variants under both rule and scripted backends. Coverage includes both issue orders, single-issue completion, absent resolved candidates, exhausted iteration budget, one-shot behavior over later calls, isolation across executions, label validity, deterministic recency/ties, and profile-disabled behavior.

The separate nine-test review-tool suite passed with localhost access. Its first sandboxed run had eight passes and one HTTP startup error; both logs are retained. No review-tool changes were needed.

Artifacts: `profile_rule.json`, `profile_scripted.json`, `original_rule.json`, `original_scripted.json`. Each records source/dataset hashes, unique per-case run IDs, original/effective configuration, event eligibility/reasons, original/replacement values, actual mutation counts, actual next Router input, selected issue, pre-action unresolved labels, and observed routing/helper actions. Mutation, receipt, and resolved-issue revisit are separate measures. `recovery_success` remains null.

Exact reproduction commands are in `commands.sh`; they use a new output directory to avoid overwriting evidence. The review-tool HTTP smoke test requires permission to bind localhost. Audits use the unchanged `support_cases_unique40.jsonl` dataset.

## Remaining limits

Scripted classification and canned helper/QA responses test mechanics, not live behavior. Rule-mode eligibility includes existing classifier mistakes. Resolution means the current ledger's evidence acceptance, not independently verified real-world issue resolution. The audit runner records boundary values and workflow history rather than full model usage/cost traces, and its temporary monkeypatch instrumentation is intended for serial audits. Any live pilot requires separate authorization and independent answer-quality assessment. Work stops here after offline validation.
