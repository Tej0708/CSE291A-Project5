# Phase 1 progress: first inventory workflow

Working branch: `fulfillment-steps`, based on `order-fulfillment-nk`.
Scope: Idea 2, first workflow (order fulfillment). Completed steps are recorded in separate local commits.

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

## Usage ledger through this checkpoint

| Run | API requests attempted | Reported tokens | Cost from reported token usage |
|---|---:|---:|---:|
| Earlier development pilot | 110 | 64,925 | $0.01224510 |
| Step 2 baseline | 150 | 99,707 | $0.01874305 |
| Total | 260 | 164,632 | $0.03098815 |

The earlier pilot's 10 rate-limited requests have unknown token usage; the cumulative token
count is the reported lower bound. Provider spending is authoritative and agrees with the
reported-token cost total at the follow-up snapshot (2026-11-02 06:25:05 UTC).

Stopped after Step 2. Next checkpoint is offline validation of fault activation and consumption.

## Remaining checkpoints

3. Review controlled fault activation, consumption, and relevance offline.

4. Validate propagation and policy-violation metrics, including affected stages, unauthorized
   actions, wasted work, and end-to-end performance; keep accidental/adversarial results separate.
5. Run the agreed small fault pilot and comparisons against full restart and always verify,
   with explicit usage bounds. Determine whether further repetitions are justified.
6. Produce the final Phase 1 results/report and reproducibility package; document limitations.

Code for metrics and comparison checkpoints was already prepared before the one-step
checkpoint preference was clarified. Its fake-model tests passing does not mean those
checkpoints or their live experiments are complete. No live fault matrix has run.
Selective recovery belongs to Phase 2.

Historical source snapshots under results/ preserve the exact experiment versions, including
prepared later-step prototypes. Active code in this commit contains the clean workflow only.
