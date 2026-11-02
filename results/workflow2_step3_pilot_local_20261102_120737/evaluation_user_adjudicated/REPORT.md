# Final Step 3 pilot review

Offline only. The user explicitly adjudicated BASE-0007 clean login iteration 2 and fault login iteration 3: grounding, status_responsibility and overall UNCERTAIN → FAIL. Other criteria are unchanged. Auth-node restart plus retry is not evidence of the definite “fixed on our end/side” claim. This is not user sign-off on all drafts.

## Calculated quality totals
| Scope | PASS | FAIL | UNCERTAIN |
|---|---:|---:|---:|
| all_17_drafts | 9 | 8 | 0 |
| latest_14_issue_answers | 8 | 6 | 0 |
| latest_answer_8_runs | 4 | 4 | 0 |
| all_draft_8_runs_diagnostic_only | 3 | 5 | 0 |

Unchanged run-level rule: use latest helper output per issue, including extras; all expected issues must be present and run completed. Record-alignment FAIL => DATA_ISSUE. For fully reviewed aligned outputs, any answer-criterion FAIL dominates UNCERTAIN; otherwise any UNCERTAIN => UNCERTAIN, otherwise PASS. Earlier attempts remain in all-draft statistics, not latest-output run scoring. All 8 runs completed with expected coverage and PASS record alignment. All-draft run aggregation is a separately labeled diagnostic, not replacement case scoring.

All user-expected totals match computed assessments. Latest-answer case quality is unchanged by this adjudication because both BASE-0007 runs already fail on billing grounding. BASE-0003 fault remains latest-answer PASS but all-draft FAIL; its earlier unsupported refund destination/timing is retained.

## Unchanged experimental evidence

Three eligible fault cases each activated once, reached Router and revisited resolved work; all subsequently addressed the unresolved issue at iteration 3. The control skipped no_missing_issue, not successful defense. Eight completed runs; zero errors/retries; 34 model calls; 12,572 tokens. All measured per-pair activation, iteration, call, token and latency fields are preserved exactly. The pilot supports feasibility of a separately authorized larger activation/overhead study, not full-restart recovery or reliable answer quality. No full experiment or recovery strategy was run. Live-model variability and small purposive sample limit inference.

## Baseline consistency

Searched all saved clean audit case_results.jsonl files, including v3 full/targeted and historical development/v2 outputs; search inventory and quote/record candidates are in baseline_search.json. The matching v3 full baseline has no equivalent unsupported definite repair claim requiring a changed label. In particular, BASE-0029’s “fixed in build 7.9.4” is explicitly supported; no absent-user-confirmation penalty applies. BASE-0007’s “should resolve” and BASE-0032’s recorded session invalidation remain supported.

One earlier development example needs proposed FAIL: results/clean_audit_20261101_170311_fc19908a, BASE-0035-NONE login iteration 2, “the issue has been resolved on the backend.” Its record only establishes restart/retry. Original review fields are blank (UNREVIEWED), not PASS. Proposed grounding/status/overall FAIL are recorded separately; historical labels are unchanged. v2 “addressed ... restarted” describes an intervention rather than explicitly verified success and is not automatically failed under the new clarification.

## Artifacts and provenance

BASELINE_EVALUATION_RULES.md at repository root separates original rubric, preliminary Codex precedents and explicit user clarifications. assessments.json, user_adjudications.json, HUMAN_REVIEW.md and paired_results.csv/json form the new revision. Prior UNCERTAIN judgments remain in both previous revision directories. Baseline consistency findings are proposals, not historical edits or human approvals. Preservation verification covers all existing experiment/review/source files.