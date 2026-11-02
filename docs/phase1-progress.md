# Phase 1 progress: first inventory workflow

Working branch: `fulfillment-steps`, based on `order-fulfillment-nk`.
Scope: Idea 2, first workflow (order fulfillment). Completed steps have separate commits.
Steps 1–3 are pushed; Step 4 is a local commit. Later-step prototypes remain uncommitted.

Work proceeds one recommended step at a time. Stop at each checkpoint and report changes,
API usage, findings, and the next step. Use `api-glm-5.3-flash`, one pilot repetition, and
preserve the $50-per-key budget. Offline tests use fake models and spend no API credits.

## Completed foundation and audit

- Reviewed the available branches and course/project documents. `order-fulfillment-nk`
  contains the fulfillment foundation; `main`, `Billing_loop_structure`, and `tej-dev`
  concern the support workflow. `main` and `Billing_loop_structure` have identical trees.
- Confirmed the attached workbook's 13 sheets match `data/dataset.json` after normalizing
  spreadsheet types. The fulfillment dataset contains 30 orders, expected to yield
  18 approvals and 12 stock rejections when each starts from the fixed inventory snapshot.
- Step 1 complete: preserve failed calls, raw responses, partial business state, dependency
  records, and terminal results. Unknown provider usage is never represented as zero.

## Step 2: clean baseline — complete

- The earlier development pilot in `results/fulfillment/clean_pilot_1` completed 20 orders;
  the remaining 10 hit rate limits. It attempted 110 API requests and reported 64,925 tokens,
  with usage unknown for the 10 rejected requests. Its prompt/schema version predates
  subsequent checker and shipping-constraint changes, so it is not pooled with the baseline.
- Added one-second request spacing and disabled SDK retries. Added a 1,024 completion-token
  default, pre-dispatch call/spend checks, and conservative reservations for unknown usage.
- Added a bounded clean-baseline runner, provider spending snapshots, public prices,
  per-order metrics, and a credential-free snapshot of executed source/data.
- Offline validation: 33 tests passed, including spend/call blocking and failed-call counting.
- Live validation completed: all 30 orders passed both task and artifact/state checks.
  Outcomes: 18 fulfilled, 12 correctly rejected for insufficient stock. No injected faults,
  failed calls, retries, or unknown usage in this baseline.
- Used 150 API requests, 88,887 input tokens, and 10,820 output tokens (99,707 total).
  Published-rate cost: $0.01874305, below the $0.05 allowance. The key's follow-up spending
  snapshot confirms the same increment after billing caught up with the last requests.
- Key spending increased from $0.01224510 to $0.03098815 of $50; remaining $49.96901185.
  Snapshots are key-wide, so future concurrent usage by others can affect the balance.
- Recorded 186 tool calls, 80.106 seconds of model-call latency, and 163.466 seconds summed
  end-to-end latency. End-to-end time includes request pacing and instrumentation.
- Verified all 35 saved source/data files against their manifest hashes and confirmed the
  result package contains no API key. This is one pilot repetition over synthetic cases.
- [Results and per-order analysis](../results/fulfillment/clean_baseline_step2/analysis.md),
  [spend and limits](../results/fulfillment/clean_baseline_step2/spend.json),
  [follow-up provider balance](../results/fulfillment/clean_baseline_step2/key_usage_followup.json),
  [artifact verification](../results/fulfillment/clean_baseline_step2/verification.json).

## Step 3: controlled fault-injection review — complete offline

- Verified all 10 default schedules against three paired clean controls. Each activates
  exactly once and has trace evidence at its intended agent, action, parser, or timeout
  boundary. Original/injected values, consumer event IDs, and dependency checks are saved.
- Fixed F-FUL-08: the old total-only planner fault did not change executor behavior. The
  schedule now sets shipping cost to zero and total to the $25 subtotal; executor copies
  the wrong shipping cost into the simulated shipment. The faulty payload remains coherent.
- Invalid stage/surface combinations, unsupported tool-call mutations, invalid paths, and
  no-op changes now fail as experiment configuration errors. They cannot be mislabeled as
  applied faults or counted as recovery trials. Failed configuration is not retried.
- Made F-FUL-04's augmentation explicit: old timestamp plus synthetic historical stock=5.
  Current stock is 0. A timestamp-only control leaves all artifacts and the task correct;
  a total-only planner control changes the quote but leaves executor actions/state unchanged.
- Nine accidental scenarios demonstrate task impact under the scripted model. Prompt
  injection demonstrates payload delivery only: the scripted model ignores instructions,
  so its correct result is not evidence of live-model resistance. Live fault tests remain pending.
- Early malformed JSON and timeout stop before the inventory agent runs. The late timeout
  occurs after stock reservation and before shipment creation. Both timeout schedules were
  exercised with their actual configured 1,500 ms delays in the saved offline review.
- Replayed all 30 saved clean-baseline responses offline. All 150 prompts, input payloads,
  and schemas matched exactly, and all final business states matched. No billed baseline
  rerun was needed. Original Step 2 results and dataset remain unchanged.
- Validation: 42 tests passed; both diagnostic controls passed; all 42 review source/data
  snapshot hashes and all 35 original baseline snapshot hashes verified.
- API usage this step: **0 requests, 0 tokens, $0**. The review blocks socket connections
  and never loads API credentials. Last confirmed provider key spending remains the Step 2
  snapshot, $0.03098815 of $50; no new balance query was made.
- [Review report](../results/fulfillment/fault_review_step3/analysis.md),
  [per-fault evidence and baseline replay](../results/fulfillment/fault_review_step3/summary.json),
  [reproducible offline runner](../experiments/review_faults.py).

## Step 4: propagation, policy, and resource metrics — complete offline

- Added explicit model-call, tool-call, and policy-audit links. Interleaved completions now
  use their own authorization decisions. Partial state changes before a failed call count;
  idempotent duplicates without another state change do not.
- Kept dependency exposure separate from observed incorrect outputs. Invalid graphs fail
  validation instead of appearing to show zero propagation. Early tool interruptions remain
  distinct from downstream semantic errors.
- Corrected wasted-work accounting for final failed/rejected calls without a successful
  retry. Distinct recomputed stages and extra model calls are measured separately; blocked
  starts do not add model calls. Incomplete starts remain explicit.
- Repair time includes failed retries and uses interval unions to avoid double-counting
  overlapping repairs. Missing token fields, latency, and policy evidence remain unknown.
- Fault-rate denominators require activation and a passing paired clean task/artifact
  control. Accidental/adversarial groups remain separate. Excluded conditions and provider
  errors still contribute to resource accounting.
- Reconciled all 30 saved baseline traces and matched the expected metrics for all 10 saved
  fault traces. Independent accounting fixtures cover interleaving, partial failures,
  duplicate actions, unknown usage, failed retries, and restart costs. All 30 baseline
  responses replayed with 150 exact prompt/input/schema matches.
- Validation: 55 tests for the standalone Step 4 commit; 60 for the full working tree,
  including uncommitted comparison prototypes. No model prompts, schemas, or dataset changed.
- API usage: **0 requests, 0 tokens, $0**. Last confirmed key spending remains $0.03098815
  of $50; no fresh balance query or live experiment was made.
- [Metric definitions](phase1-metrics.md),
  [saved review](../results/fulfillment/metric_review_step4/analysis.md),
  [per-trace and fixture checks](../results/fulfillment/metric_review_step4/summary.json).

## Usage ledger through this checkpoint

The Git split preserves the exact historical experiment snapshots. Those archives include
prepared later-step prototypes from the original execution environment; they are evidence,
not active implementations added by the corresponding checkpoint commit. Each committed
step is independently runnable. See [commit validation](commit-checkpoints.md).

| Run | API requests attempted | Reported tokens | Cost from reported token usage |
|---|---:|---:|---:|
| Earlier development pilot | 110 | 64,925 | $0.01224510 |
| Step 2 baseline | 150 | 99,707 | $0.01874305 |
| Step 3 offline review | 0 | 0 | $0 |
| Step 4 offline metric review | 0 | 0 | $0 |
| Total | 260 | 164,632 | $0.03098815 |

The earlier pilot's 10 rate-limited requests have unknown token usage; the cumulative token
count is the reported lower bound. Provider spending is authoritative and agrees with the
reported-token cost total at the follow-up snapshot (2026-11-02 06:25:05 UTC).

Stopped after Step 4. Next: finish the comparison runners and run the agreed bounded live
pilot with one repetition and explicit spending/call limits. No Step 5 experiment has begun.

## Remaining checkpoints

5. Run the agreed small fault pilot and comparisons against full restart and always verify,
   with explicit usage bounds. Determine whether further repetitions are justified.
6. Produce the final Phase 1 results/report and reproducibility package; document limitations.

Comparison code was prepared before the one-step checkpoint preference was clarified.
Its fake-model tests passing does not mean the comparison checkpoint or its live experiments
are complete. No live fault matrix has run.
Selective recovery belongs to Phase 2.
