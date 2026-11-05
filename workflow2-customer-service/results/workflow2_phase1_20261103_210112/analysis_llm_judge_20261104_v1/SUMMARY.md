# Workflow 2 saved-answer LLM evaluation

Status: INCOMPLETE / BLOCKED



No original experiments are executed by this runner. Existing results and human judgments are read-only. The user authorized an available non-GPT judge. GLM Flash is used; shared answer/judge model bias is a limitation.

| Scope | Expected | Evaluated | PASS | FAIL | UNCERTAIN | DATA_ISSUE | Evaluation errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary_draft | 560 | 558 | 443 | 115 | 0 | 0 | 2 |
| primary_bundle | 240 | 240 | 180 | 53 | 0 | 7 | 0 |
| infrastructure_archive_draft | 6 | 6 | 3 | 3 | 0 | 0 | 0 |
| infrastructure_archive_bundle | 5 | 5 | 0 | 5 | 0 | 0 | 0 |

Individual primary answers include 480 retained and 80 discarded drafts. Archive answers and incomplete archive bundles are separate from the 240-slot experiment. Missing evaluations are NOT_EVALUATED, never answer FAIL or PASS.

Candidate: `api-glm-5.3-flash` at `https://tritonai-api.ucsd.edu/v1`; model actually used: api-glm-5.3-flash. Public endpoint rates: $0.15000000/M input and $0.5000000/M output tokens. These are gateway catalog prices, not assumed direct OpenAI rates. The current key's model list is authoritative for access.

Paid requests: 748. Accounted cost: $1.13121635. Remaining ceiling: $1.86878365. Full-run planning estimate: $1.1070, based on bytes/3 input-token approximation and 1,500 output tokens/request; this is not a guaranteed quote. Actual reservation uses full catalog input capacity plus the configured output cap, published text-token rates. USD 1.00 remains an unspent precautionary holdback. No guarantee is claimed for unreported provider-side charges.

Start with README.md and preflight.json. review_sheet.csv contains all expected items, judgment evidence and separate UNREVIEWED human fields. judgments.jsonl contains only valid mapped judgments; empty means none evaluated. unfinished_items.csv lists exact outstanding IDs. human_followup_queue.csv contains assessed non-PASS items, evaluation errors and a seed-20261104 sample of PASS; a zero-row queue is not approval of pending items. run_quality.csv combines retained answer and bundle assessments. All eventual conclusions are LLM-assessed, never human-verified. Latency, fault activation, calls and experiment tokens remain deterministic outputs from analysis_offline_20261104_3d072433_en; the judge does not estimate them.
