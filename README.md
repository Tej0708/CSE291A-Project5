# CSE 291A Multi-Agent Failure Recovery 

This branch implements the order-fulfillment workflow and Phase 1 experiment tooling.
The clean baseline is complete. Fault injection and comparison methods remain later
checkpoints; no live fault experiments have run. See
[Phase 1 progress](docs/phase1-progress.md) for completed work and the next step.

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

## Running clean experiments

These are purely for establishing baseline behavior that later fault-injection runs will be compared against.

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

TODO:
When the support workflow is added, it can be registered in `workflows/registry.py` and called
through the same CLI, for example:

```bash
python main.py --workflow support --task-id TKT-2001
```

## Logs and metrics

Each run writes one JSONL trace to:

```text
logs/<workflow>/<task_id>/<run_id>.jsonl
```

Each JSONL line is one timestamped event such as a tool result or an agent completion. An
agent-completion record contains the produced `artifact_id`, `producer_agent`, and its `sources`.
Each source contains a `source_type` and `source_id` that points to an earlier record in the
same trace.

`experiments/metrics.py` reads a completed JSONL trace through `summarize_trace()` and
aggregates:

- model-call count
- tool-call count
- input/output/total tokens
- total model latency
- end-to-end (`e2e`) workflow latency

`experiments/run_clean.py` calls this automatically after every run, and `main.py` prints the
most useful summary fields.

To pretty-print a trace with `jq`:

```bash
jq '.' logs/fulfillment/ORD-1001/<run_id>.jsonl
```

Or render the JSONL records as one JSON array:

```bash
jq -s '.' logs/fulfillment/ORD-1001/<run_id>.jsonl
```

## Checker

`workflows/fulfillment/checker.py` is called by `FulfillmentWorkflow.run()` after the Executor's
tool actions finish. It independently checks the agent outputs and final mutable state against
the dataset/oracle rules. The checker is not an LLM and is not just for logging: it determines
whether a clean or future fault-injected run actually produced the correct result.

`fulfillment_ground_truth` is available only to the checker and is never passed to an LLM agent.

## Automatic tests

The tests use a deterministic fake model, so they consume no TritonAI credits:

```bash
python -m pytest -q
```

They execute all 30 fulfillment cases and verify the workflow, mutable state, deterministic
checker, source/dependency tracking, and that every source ID resolves in the same trace.

## Current deterministic tools 

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
