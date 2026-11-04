# CSE 291A Multi-Agent Failure Recovery 

This branch implements the order-fulfillment workflow for studying fault propagation
and recovery in a multi-agent system. It includes controlled fault injection,
dependency and action tracing, full-restart and always-verify recovery baselines,
held-out evaluation workloads, live experiment runners, and automated result analysis.

The clean baseline, offline validation, live pilot, and three-repetition held-out
baseline evaluation have been completed.

## Setup (bash/macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your TritonAI key and the base URL in `.env`.

## Order Fulfillment Workflow

```text
Inventory Agent ─┐
Pricing Agent ───┼─> Planning Agent -> Executor Agent -> simulated tools/state
Shipping Agent ──┘
```

An **agent artifact** is the structured intermediate result produced by an agent. Each artifact
records its `sources`, which can reference earlier agent artifacts or tool-result events in the
same JSONL trace.

Each task execution is one isolated **run**. A run creates fresh mutable state from the
immutable `data/dataset.json`, so one task/run cannot change the starting state of another.

## Clean baseline and basic runs

The clean baseline establishes fault-free behavior and resource usage for comparison
with fault-injected and recovery runs.

The recommended budgeted baseline command runs all 30 orders once, checks key spending,
and stops before exceeding 150 API calls or its conservative $0.05 local estimate:

```bash
python -m experiments.clean_baseline \
  --output-dir results/fulfillment/clean_baseline_step2 \
  --max-api-calls 150 --max-cost-usd 0.05
```

Use a new output directory for each experiment. The runner saves provider spending before
and after, public token prices, per-order results, source hashes, an executed-source snapshot,
and full traces. Provider billing remains authoritative; unknown token usage retains a
conservative cost reservation. The user's key budget is $50. The default model is
`api-glm-5.3-flash`, with one-second request spacing, no SDK retries, and a 1,024-token
completion cap. `MAX_COMPLETION_TOKENS` can override that cap.

The general-purpose commands below do not apply the baseline runner's dollar/call limit.

Run one fulfillment task:

```bash
python main.py --workflow fulfillment --task-id ORD-1001
```

`--order-id` remains an alias for fulfillment-only usage:

```bash
python main.py --order-id ORD-1001
```

Run several tasks:

```bash
python main.py --workflow fulfillment \
  --task-id ORD-1001 \
  --task-id ORD-1002
```

Run every task in the selected workflow once:

```bash
python main.py --workflow fulfillment
```

Repeat each selected task:

```bash
python main.py --workflow fulfillment --task-id ORD-1001 --runs 5
```

## Paired live fault/recovery experiments

A separate [Workflow 1 evaluation dataset](docs/fulfillment-evaluation.md) provides
30 new orders and 10 matching fault schedules, with commands for selecting them.

Use Python 3.10 or newer. Start with the offline smoke test (no API calls):

```bash
python -m experiments.run_live_fault_recovery --scripted \
  --fault-id F-FUL-01 --output-dir results/fulfillment/fault_smoke_01
```

The runner pairs clean and injected runs under `unprotected`, `full_restart`, and
`always_verify`, saving trial metrics, comparisons, traces, and completion status.
See [live experiment instructions](docs/live-fault-recovery.md) for budgeted live
commands and interpretation limits. 

Run the held-out evaluation with three repetitions:

```bash
python -m experiments.run_live_fault_recovery \
  --dataset data/fulfillment_eval.json \
  --faults-file data/fulfillment_eval_faults.json \
  --repetitions 3 \
  --max-api-calls 1200 \
  --max-cost-usd 3.00 \
  --output-dir results/fulfillment/eval_live_final_r3
```

## Logs and metrics

Each workflow attempt writes a JSONL trace under:

```text
logs/fulfillment/<TASK_ID>/<run-id>.jsonl
```

Each line is a timestamped event such as a model call, tool call, agent artifact, verification event, fault-injection event, or state change. Artifact and tool-event IDs are used to preserve dependency relationships within the trace.

Experiment runners summarize these traces into per-trial and paired metrics. Recorded measurements include:

- model, tool, and verification call counts
- input/output token usage and estimated inference cost
- end-to-end and recovery latency
- fault activation, downstream exposure, and observed corruption
- affected stages and dependency propagation
- policy-invalid actions attempted or executed
- recomputed and discarded work during recovery

The held-out live evaluation additionally writes files such as `trials.jsonl`, `trials.csv`, `paired.csv`, `summary.json`, and `spend.json`. These preserve trial-level results and matched clean-vs-fault comparisons.

After an evaluation finishes, you can additionally run:

```bash
python -m experiments.analyze_live_fault_recovery \
  results/fulfillment/eval_live_final_r3             # path to the completed evaluation 
```

The analyzer writes `analysis/summary.md` for a human-readable overview, along with CSV/JSON tables for detailed analysis. Raw traces remain the underlying audit evidence.

For detailed metric definitions and accounting rules, see [docs/phase1-metrics.md](docs/phase1-metrics.md).

Useful trace inspection commands:

```bash
# Pretty-print one JSONL event at a time
jq '.' logs/fulfillment/<TASK_ID>/<run-id>.jsonl

# Load the full trace as a JSON array
jq -s '.' logs/fulfillment/<TASK_ID>/<run-id>.jsonl
```

## Checker

`workflows/fulfillment/checker.py` is called by `FulfillmentWorkflow.run()` after the Executor's
tool actions finish. It independently checks the agent outputs and final mutable state against
the dataset/oracle rules. The checker is not an LLM and is not just for logging: it determines
whether a clean or fault-injected run actually produced the correct result.

`fulfillment_ground_truth` is available only to the checker and is never passed to an LLM agent.

## Automatic tests

```bash
python -m pytest -q
```

The test suite uses deterministic fake/scripted models and consumes no TritonAI credits.
It covers the fulfillment workflow, checker, dependency/source tracking, fault injection,
recovery policies, evaluation data, experiment accounting, and related invariants.

## Offline fault-injection review

```bash
python -m experiments.review_faults \
  --output-dir results/fulfillment/fault_review_new \
  --baseline-dir results/fulfillment/clean_baseline_step2
```

This command blocks network connections and uses no API credentials or credits. It checks
10 fault schedules, paired clean controls, timestamp-only and total-only diagnostic cases,
and exact-request replay of all 30 saved baseline traces. It preserves source hashes,
traces, and a report in the new output directory. Scripted results establish harness
behavior, not live-model robustness; prompt-injection evidence is limited to delivery.

## Offline metric review

```bash
python -m experiments.review_metrics \
  --output-dir results/fulfillment/metric_review_new
```

This command blocks network connections. It reconciles 30 saved baseline traces, checks
the expected metrics for 10 saved fault traces, verifies independent accounting fixtures,
and replays all 30 saved baseline responses. See [metric definitions](docs/phase1-metrics.md).
Unknown usage, missing action evidence, and incomplete calls stay explicit. The scripted
fault results validate measurement behavior; they are not live-model failure rates.

## Deterministic Tools 

### Order Fulfillment Workflow

Read-only tools:
- `get_order_context`
- `get_inventory_inputs`
- `get_pricing_inputs`
- `get_shipping_inputs`

State-changing tools used by the Executor:
- `reserve_inventory`
- `create_shipment`
- `update_order_status`

`dataset.json` is never mutated. Each run creates a new `FulfillmentState`.

## Recovery baselines (fulfillment)

Use Python 3.10 or newer. Select a policy with `--mode full_restart` or
`--mode always_verify` on `main.py`; the default remains `unprotected`.

- `full_restart` is an oracle baseline: if a fault was actually injected
  (`fault_applied=true`), it permits one complete retry from fresh dataset state,
  even when the first attempt was correct or ignored the injected content.
  Clean runs and faults that were never applied do not trigger a restart.
  Infrastructure, configuration, programming, and budget errors still block retries.
- `always_verify` independently checks every produced artifact after injection and
  before downstream consumption, including executor actions before dispatch.
  A rejected output or stage exception permits one fresh stage invocation and a
  second verification. A second failure stops execution. Retries read inputs again
  and regenerate outputs with the model; reference answers are never substituted.
  State-changing tool failures stop the attempt rather than retrying partial effects.

Both policies share one `RunBudget` across retries. Configuration, provider
infrastructure, and budget errors are not retried. Faults are transient: an injected
fault occurs once and is absent on a full restart. Resetting simulated state does
not implement compensation for real external actions.

`WorkflowResult.attempts` preserves each full attempt and its trace. Clean-run
summaries include all attempt paths and sum their resource metrics. Verification
records include elapsed time and rejected artifact dependencies; deterministic
verification consumes a tool-budget unit and no model call.

Run the offline comparison matrix (clean controls plus every default fault under
all three modes) without API credits:

```bash
python -m experiments.compare_recovery --output-dir /tmp/recovery-review
```

The new directory contains `results.json` and all attempt traces, including
propagation, discarded-call accounting, verification costs, and retry costs.
Scripted outcomes validate the recovery harness; they should not be interpreted 
as live-model recovery rate.
