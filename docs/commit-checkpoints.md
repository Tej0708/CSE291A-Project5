# Completed-step commits

Branch: `fulfillment-steps`. Base: `origin/order-fulfillment-nk` at `1687b38`.

| Step | Commit subject | Standalone validation |
|---|---|---|
| 1 | `fix(step1): preserve workflow failure traces` | 7 offline tests |
| 2 | `feat(step2): add budgeted clean baseline` | 16 offline tests; 30 saved-response replays with 150 exact request matches |
| 3 | `feat(step3): validate controlled fault injection` | 37 offline tests; all 10 fault schedules, both diagnostic controls, and 30 baseline replays pass |

The standalone test counts differ from the earlier 33/42-test development checkpoints:
those checkpoints also included tests for prepared later-step code. The complete working
tree retains those prototypes and its 42-test suite. No API calls were made to split or
validate the commits.

Step 1 preserves model/tool failures, partial state, token-usage uncertainty, and terminal
results. Step 2 adds budget controls, stronger correctness checks, and the recorded clean
baseline. Step 3 adds validated one-shot injections, consumer evidence, controls, and exact
saved-response replay. It also limits pytest discovery to `tests/`, preventing archived test
copies under `results/` from colliding with active tests.

Historical manifests, traces, and source snapshots are unchanged. They retain the code
actually executed before the Git split, including prototypes already present at that time.
The active code in each commit excludes the uncompleted propagation/recovery implementation.
Shared trace reading and provider error types live in `core/`, so completed steps do not
depend on those future modules.

Pending working-tree changes include propagation/reporting and comparison runners,
verification/retry paths, expanded metrics, and their tests. These belong to Steps 4–6;
they are not represented as completed by this history. No live fault experiment has run.

Validation commands for the committed Step 3 tree:

```bash
python -m pytest -q
python -m experiments.review_faults \
  --output-dir /tmp/fulfillment-fault-review-new \
  --baseline-dir results/fulfillment/clean_baseline_step2
```

Use a new output directory for every review. Stop at this checkpoint before starting Step 4.
