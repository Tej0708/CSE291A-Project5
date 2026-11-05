# Workflow 2: results ready for team review

The offline audit is complete. **All 240 planned slots completed and passed integrity checks. The data support descriptive execution and overhead analysis; answer quality and semantic recovery success still require human review. No reruns are currently needed.**

Repository: `Tej0708/CSE291A-Project5`; branch: `Billing_loop_structure`; audited commit: `3d072433f7dda2483fd57f0abe02ad336a7f7ba2`.

| Completeness measure | Count |
|---|---:|
| Completed primary slots | 240/240 |
| Failed / error / budget_exhausted | 0 / 0 / 0 |
| Partial / not_run | 0 / 0 |
| Extra / duplicate slots | 0 / 0 |
| Archived infrastructure attempts, accounted separately | 5 |
| Activated fault slots | 180/180 |

Mean end-to-end latency in milliseconds; each cell represents 20 different cases, each executed once:

| Scenario | unprotected | full_restart | always_verify |
|---|---:|---:|---:|
| NONE | 2103 | 2188 | 2031 |
| QA_CORRUPTION | 3703 | 5630 | 2900 |
| HELPER_CORRUPTION | 3119 | 4856 | 2752 |
| TIMEOUT | 2644 | 2187 | 2796 |

Under QA corruption, full_restart did not trigger a restart; always_verify blocked propagation in 20/20 cases. Overall, 100/180 fault runs involved policy repair and 80/180 continued naturally. Neither category establishes semantic success. Single-repetition latency differences do not prove stable speedups.

Start with [the full report](START_HERE.md), then [the review guide](HUMAN_REVIEW_GUIDE.md). Review the complete [560-row answer table](human_review_complete.csv): 480 retained answers and 80 discarded drafts. The [390-row priority list](human_review_priority.csv) only sets review order; the remaining 170 answers also require review. All human fields remain UNREVIEWED. Six archived infrastructure drafts are separate.

The [Phase 1 evidence mapping](PHASE1_REQUIREMENTS.md) identifies two substantive remaining items: human quality review and confirmation of official course requirements, which were not found in the repository. The Python 3.14 floating-point discrepancy is documented; the unchanged strict verifier passes under Python 3.9.

The original audit passed 22 offline tests and two review-adapter tests. Translation validation verifies unchanged measurements, review identities/hashes, and all 2,456 raw evidence files. No paid API experiments, reruns, commits, or pushes were performed. See [the complete file index](FILES.md) for logs, detailed paired comparisons, token accounting, and reproducibility scripts.
