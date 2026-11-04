# Workflow 2 offline audit report — English edition, November 4, 2026

**All 240 unique experimental slots completed and passed integrity verification. The results support descriptive execution and overhead analysis. Answer quality and semantic recovery success remain pending human review. No slots are missing and no reruns are needed.**

## Provenance and isolation

- Repository: https://github.com/Tej0708/CSE291A-Project5.git; branch: `Billing_loop_structure`.
- Commit actually fetched and inspected: `3d072433f7dda2483fd57f0abe02ad336a7f7ba2`.
- Experiment checkout: `/Users/yanghede/.codex/worktrees/workflow2-offline-audit/CSE291A-Project5` (independent detached worktree).
- Raw results read: `/Users/yanghede/.codex/worktrees/workflow2-offline-audit/CSE291A-Project5/results/workflow2_phase1_20261103_210112`.
- English delivery directory: `/Users/yanghede/.codex/worktrees/workflow2-offline-audit/CSE291A-Project5/results/workflow2_phase1_20261103_210112/analysis_offline_20261104_3d072433_en`. This edition translates the earlier audit package and preserves its numerical results and review identities. The earlier Chinese package remains available in the original main checkout. Its older experimental results were **not** used for this audit.
- The original main checkout was initially clean and was not pulled, merged, or checked out to another branch. No commits or pushes were made. No applicable AGENTS.md was found in the checked ancestors or target tree.
- Frozen manifest SHA256: `ba64bc213768385ec01592bb1491de7bb9313111f57f366b3d6965e9eb45b428`; byte-identical to phase1_v1/full_manifest.json.
- Historical verification logs and provenance snapshots are retained as evidence of the original audit; translation_validation.json records this edition's checks.

## Completeness and usability

| State | Primary experimental slots |
|---|---:|
| completed | 240 |
| failed | 0 |
| error | 0 |
| budget_exhausted | 0 |
| partial | 0 |
| not_run | 0 |
| Extra slots / duplicate slots / duplicate run IDs / duplicate event IDs | 0 / 0 / 0 / 0 |

All 240 unique (case, scenario, policy, repetition) tuples were checked individually. Identity records, receipt/result SHA256, result/trace consistency, recomputed answers, metrics files, provider journals, run/event/call links, logging sanity, model settings, budgets, and key source hashes passed. All five continuation plans passed checks against their interrupted and previously completed evidence. Hashes of all 2,456 raw files remained unchanged. slots_240.csv lists every slot; none was silently excluded.

Recorded runtime Git revisions are 73959a0… (37 runs), e03500c… (20), and 2b113f9… (183). These differ from the uploaded commit: the runs must not be described as executed at one Git HEAD. Each result's four recorded key source hashes match the audited checkout. Manifest/continuation source and data checks pass; the authorized source differences are continuation/logging runner revisions. All runs use api-glm-5.3-flash, temperature 0, zero SDK retries, 40/40/40 per-run budgets, a four-iteration limit, and one repetition. Returned provider model labels agree. Complete per-run endpoint and Python/SDK dependency locks are unavailable; exact environment identity is therefore not established. The handoff specifies TritonAI and Python 3.9.

The first strict verifier run under default Python 3.14.3 failed because seven slots differ in the last bits of model_latency_ms / known_model_latency_ms floating-point sums (approximately 1e-13 to 1e-12 ms). The unchanged strict verifier exits 0 under Python 3.9.6. Neither raw results nor tolerances were changed. Both logs and exact differences are retained. This is interpreter-dependent numerical reproduction, not an API or answer failure.

## Design and metric definitions

Workflow: classification → Router → Billing/Technical Helper (read simulated records and generate an answer) → QA → Router, continuing according to the issue ledger. There is no final answer-composition agent. The 20 cases are all structurally eligible mixed billing→technical cases among 40 base cases, not a random population sample. They cover ten issue types but have limited route diversity, and some were reused from pilots. Seed 42, clean-first ordering within each case, and policy rotation are frozen; service load and execution timing may confound latency comparisons.

NONE is the same-policy clean control. QA_CORRUPTION changes the QA→Router missing-issue value once. HELPER_CORRUPTION corrupts a helper record once. TIMEOUT returns a synthetic timeout status once; it does not measure real network waiting or deadline behavior. Faults are not reinjected during retry/restart. unprotected continues naturally; full_restart restarts on its implemented triggers and performs terminal checks; always_verify performs deterministic stage checks, rejection, and local retry. Verification does not invoke an additional judge model, although repair can invoke a model again.

Definitions follow phase1_v1/METRICS.md and the original reducer. Model, business-tool, and verification dispatches are separate; business-tool counts include reference reads logged as tools. Total latency is end-to-end wall time. Recovery latency is the union of recovery intervals and must not be added to total latency. Discarded calls are explicitly marked by the ledger. waste_union additionally combines repeated calls without double counting. Known token subtotals are not complete usage; USD remains null without pricing.

## Observed results

| Scenario | Policy | Observed / planned | Activated / planned fault slots | Policy repair / runs | Model / business / verification calls (totals) | Mean total latency (ms) | Mean recovery interval (ms) | Discarded calls | Reported tokens |
|---|---|---|---|---|---|---|---|---|---|
| NONE | unprotected | 20/20 | N/A | 0/20 | 80 / 80 / 0 | 2103.2 | 0.0 | 0 | 29912 |
| NONE | full_restart | 20/20 | N/A | 0/20 | 80 / 120 / 40 | 2188.4 | 0.0 | 0 | 29897 |
| NONE | always_verify | 20/20 | N/A | 0/20 | 80 / 120 / 80 | 2031.0 | 0.0 | 0 | 29898 |
| QA_CORRUPTION | unprotected | 20/20 | 20/20 | 0/20 | 120 / 120 / 0 | 3702.9 | 0.0 | 60 | 45182 |
| QA_CORRUPTION | full_restart | 20/20 | 20/20 | 0/20 | 120 / 160 / 40 | 5629.8 | 0.0 | 60 | 45234 |
| QA_CORRUPTION | always_verify | 20/20 | 20/20 | 20/20 | 100 / 120 / 100 | 2899.6 | 308.5 | 20 | 33906 |
| HELPER_CORRUPTION | unprotected | 20/20 | 20/20 | 0/20 | 80 / 80 / 0 | 3118.7 | 0.0 | 0 | 31644 |
| HELPER_CORRUPTION | full_restart | 20/20 | 20/20 | 20/20 | 160 / 229 / 69 | 4856.2 | 2281.6 | 160 | 61561 |
| HELPER_CORRUPTION | always_verify | 20/20 | 20/20 | 20/20 | 80 / 180 / 100 | 2752.3 | 611.9 | 40 | 29938 |
| TIMEOUT | unprotected | 20/20 | 20/20 | 0/20 | 100 / 120 / 0 | 2644.3 | 0.0 | 0 | 34471 |
| TIMEOUT | full_restart | 20/20 | 20/20 | 20/20 | 100 / 160 / 40 | 2186.7 | 1863.2 | 60 | 33137 |
| TIMEOUT | always_verify | 20/20 | 20/20 | 20/20 | 80 / 180 / 100 | 2795.6 | 1377.1 | 40 | 29902 |

Each group contains 20 different cases with one execution each. Calls and tokens are group totals; latency values are arithmetic means across 20 runs. Mean recovery latency includes observed zero intervals for runs with no policy repair. Available sample counts, medians, states, and denominators are recorded in scenario_policy_summary.csv/json.

- Fault activation: 180/180; inactive: 0/180; unknown: 0/180. Activation is N/A for the 60 clean runs.
- Policy-triggered repair: 100/180; natural continuation: 80/180. The 100 repair intervals have structural accepted/completed outcomes. **Semantic success or failure is not yet established.** Neither structural completion nor natural continuation is counted as semantic recovery success.
- QA corruption: unprotected and full_restart each show propagation and repeated work in 20/20 runs. full_restart did not actually restart. always_verify blocked propagation in 20/20 runs.
- Helper corruption: unprotected accepted the corrupted record in 20/20 runs; full_restart propagated it before policy repair in 20/20; always_verify blocked it in 20/20. Residual answer contamination requires human review.
- TIMEOUT: unprotected continued naturally in 20/20 runs; full_restart and always_verify each performed policy repair in 20/20. This does not demonstrate robustness to real network timeouts.
- Observable detection: 120/180; detection is not equivalent to policy repair. The decisive reviewed-clean denominator is zero, so clean semantic success is unavailable, not 0%. All 240 run-level and 560 draft-level human quality assessments remain pending.

## Paired comparisons

| Scenario | Policy | Available / planned pairs | Mean latency delta vs same-scenario unprotected (ms) | Mean latency delta vs own clean control (ms) |
|---|---|---|---|---|
| NONE | unprotected | 20/20 | 0.0 | 0.0 |
| NONE | full_restart | 20/20 | 85.2 | 0.0 |
| NONE | always_verify | 20/20 | -72.2 | 0.0 |
| QA_CORRUPTION | unprotected | 20/20 | 0.0 | 1599.7 |
| QA_CORRUPTION | full_restart | 20/20 | 1926.9 | 3441.5 |
| QA_CORRUPTION | always_verify | 20/20 | -803.3 | 868.5 |
| HELPER_CORRUPTION | unprotected | 20/20 | 0.0 | 1015.5 |
| HELPER_CORRUPTION | full_restart | 20/20 | 1737.5 | 2667.9 |
| HELPER_CORRUPTION | always_verify | 20/20 | -366.4 | 721.3 |
| TIMEOUT | unprotected | 20/20 | 0.0 | 541.1 |
| TIMEOUT | full_restart | 20/20 | -457.6 | -1.6 |
| TIMEOUT | always_verify | 20/20 | 151.3 | 764.6 |

All pairs match case and repetition. vs_unprotected holds scenario fixed; vs_own_clean holds policy fixed. paired_slots.csv preserves each delta and percentage; paired_summary.csv includes calls/tokens and counts of negative, zero, and positive differences. Self-comparison zeros are identities. Twenty different cases are not twenty repetitions of the same case. These differences do not establish stable latency gains. For example, always_verify has lower mean latency than unprotected under QA corruption, but higher latency under TIMEOUT; service timing and load are not controlled.

## Infrastructure errors: separate accounting

| Slot | Model calls | Known token subtotal | Unknown failed-call usage |
|---|---|---|---|
| BASE-0004__HELPER_CORRUPTION__full_restart__r1 | 7 | 2347 | 1 calls |
| BASE-0007__QA_CORRUPTION__always_verify__r1 | 4 | 899 | 1 calls |
| BASE-0011__NONE__full_restart__r1 | 3 | 706 | 1 calls |
| BASE-0020__TIMEOUT__full_restart__r1 | 1 | 0 | 1 calls |
| BASE-0027__HELPER_CORRUPTION__unprotected__r1 | 3 | 792 | 1 calls |

All five archived attempts ended in error / RateLimitError HTTP 429; their primary slots completed after infrastructure re-execution. These are neither policy recovery nor additional experimental repetitions. The archives contain 18 model calls and 4744 known tokens, plus five failed calls with unknown usage. Primary reported tokens total 434682, scoped to application responses. The combined operational known subtotal is 439426; complete token usage and USD cost remain unavailable. Internal provider attempts and underlying consumption are also unobservable.

The first archive lacks provider code/message/Retry-After, so its cause cannot be narrowed further. The other four explicitly record request throttling, limit 100, remaining 0, a reset time, and Retry-After=60. This supports request rate limiting, not a claim of exhausted credit or total quota. Original error text is preserved in infrastructure_audit.json.

## Phase 1 delivery and remaining work

| Requirement | Existing evidence | Completion status | Gap / next action |
|---|---|---|---|
| Official Phase 1 rubric, submission format, and deadline | No original course instructions or PDF found; phase1_v1/COVERAGE.md is an internal project mapping | Requirements unclear | Confirm against course materials; do not treat an internal checklist as the official grading rubric. |
| Workflow and task definition | README.md; csa_workflow/recovery.py; Router → Billing/Technical → QA → Router | Completed | Services read deterministic fixtures; no real refunds or user-device repairs are executed. |
| Dataset selection and applicability | phase1_v1/selected_population.json, applicability.json, full_manifest.json | Completed | The selected 20/40 cases are all structurally eligible mixed-issue cases. Disclose selection bias, pilot reuse, and limited route diversity. |
| Frozen design and clean baseline | Manifest: 20 × 4 × 3 × 1; NONE: 60/60 completed | Awaiting human review | Semantic quality of 60 clean runs and their 120 retained drafts remains unreviewed. |
| Fault injection and activation | 180/180 ACTIVATED; exactly one mutation per fault run; paths in measurements.json | Completed | TIMEOUT is an immediate synthetic status. Adversarial inputs, stale outputs, and real transport deadlines are outside this design. |
| unprotected / full_restart / always_verify | Frozen RecoveryRunner; 240 identity/receipt/source checks; existing offline tests | Completed | full_restart does not trigger a restart under QA_CORRUPTION; do not describe that outcome as successful restart recovery. |
| 240-slot execution completeness | slots_240.csv, integrity.json, verifier_python39.txt | Completed | 240 completed; all five other execution states are zero; no extra or duplicate slots; no reruns needed. |
| Version, logging, and continuation audit | Five validated continuation plans; hashes for 2,456 raw files; matching key source hashes across three runtime Git revisions | Completed | A complete dependency lock and endpoint were not recorded per run; exact environment equivalence is not established. |
| Metrics and within-case pairing | phase1_v1/METRICS.md; scenario_policy_summary.csv; paired_slots.csv; paired_summary.csv | Completed | Single-repetition descriptive latency only; no stable-speedup or significance claims. Unknown USD and failed-call usage remain unavailable. |
| Propagation, discarded calls, and recovery intervals | measurements.json paths/waste/policy_recovery; grouped repair latency | Completed | Structural accepted/completed does not establish semantic recovery success; overlapping timing measures must not be added. |
| All drafts and latest-per-issue answer quality | 560 review rows: 480 retained, 80 discarded; six infrastructure drafts separate | Awaiting human review | Assess all five criteria with identity/hash checks and reviewer provenance. Human fields remain UNREVIEWED; second-review FAIL/UNCERTAIN decisions. |
| Recovery success and clean-PASS conditional analysis | 180 fault runs: 100 policy-triggered repairs, 80 natural continuations | Awaiting human review | Semantic success is unavailable; the decisive reviewed-clean denominator is zero. Do not report 0/0 as 0%. |
| Cross-version Python reproducibility | Strict Python 3.14 verification differs in floating-point last bits for seven slots; unchanged Python 3.9.6 verification passes | Optional compatibility repair | Reproduction with Python 3.9 is complete. Future interpreter support needs a separately versioned numerical protocol, not edits to raw results or weaker checks for this study. |

## Human review entry point

Read HUMAN_REVIEW_GUIDE.md. Use human_review_priority.csv to locate priority event IDs, and enter decisions in a **separately saved copy** of human_review_complete.csv. The complete table contains 560 rows: 480 retained answers determine latest-per-issue/run quality and semantic recovery; 80 discarded drafts support historical contamination, failure-path, and all-draft analysis. Discarded judgments do not replace retained judgments.

The priority table contains 390 rows (340 retained, 50 discarded). Its keyword, record-difference, and recovery-boundary flags are screening suggestions, not established failures or automatic approval of other rows. Six infrastructure drafts are in a separate table and excluded from primary quality denominators.

No human review files were found for this experiment. Historical baseline/pilot judgments concern different run/event identities and remain interpretation precedents rather than approval of these answers. All five criteria and human_verdict remain UNREVIEWED. Machine suggestions are separate; reviewer, timestamp, and rationale are blank.

## Code and validation

No frozen experimental source was modified. The delivery includes audit_offline.py (read-only audit, aggregation, review export), build_report.py (English document generation), and import_human_reviews.py (offline identity/hash validation and new-directory analysis). Original analyzer outputs remain in existing_analysis/. The original audit passed 22 offline tests, including the scripted 240-run fixture; these were not paid provider experiments. The historical continuation regression tied to the old 37/1/202 snapshot was not rerun. Two adapter tests passed: blank reviews do not become PASS, and a modified run ID is rejected. All raw evidence hashes remained unchanged. FILES.md indexes this edition; translation_validation.json records evidence-preservation and language checks.
