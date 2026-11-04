# Workflow 1 live fault/recovery experiments

This file and `run_live_fault_recovery.py` were added for **Workflow 1 (fulfillment)** only.

## 1. Set up

From the repository root:

Use Python 3.10 or newer; activate an environment created with that version.

```bash
pip install -r requirements.txt
cp .env.example .env  # only if you don't already have .env
```

Put your authorized TritonAI/OpenAI-compatible API credentials in `.env`. Never commit `.env`. The default gateway/model are configured in `core/config.py`. Do not paste API keys into command-line arguments.

## 2. Run the offline smoke test first (no API calls)

```bash
python -m experiments.run_live_fault_recovery --scripted \
  --fault-id F-FUL-01 --output-dir results/fulfillment/fault_smoke_01
```

This runs 6 trials (one clean/fault pair for each of three modes) using deterministic scripted responses. It confirms the experiment plumbing, **not LLM robustness**. Choose a NEW output directory every time.

## 3. Run a small LIVE pilot

```bash
python -m experiments.run_live_fault_recovery \
  --fault-id F-FUL-01 --fault-id F-FUL-05 \
  --max-api-calls 75 --max-cost-usd 0.10 \
  --output-dir results/fulfillment/live_fault_pilot_01
```

This executes paired clean/fault controls for every selected fault under `unprotected`, `full_restart`, and `always_verify`; no mocked model is used. `F-FUL-05` may be an adversarial case; consult the manifest. This specific pilot schedules 12 trials. API calls and estimated cost are conservatively guarded, **not guaranteed actual provider charges**. The tool checks TritonAI key budget and currently published rates prior to a live run; other gateways are not supported by the built-in price checker.

## 4. Full declared matrix (estimate API budget first)

```bash
python -m experiments.run_live_fault_recovery \
  --max-api-calls 450 --max-cost-usd 1.00 \
  --output-dir results/fulfillment/live_fault_matrix_01
```

With ten default faults and three modes, the full matrix has **60 trials** (30 matched pairs), with each clean paired to the same order/mode/fault ID. Shared live API cap applies to all trials. Different modes can require different call counts due to retries/restarts. The runner stops when infrastructure errors, cost/call guards, or unexpected metric errors occur; it does **not** silently replace results. The `completion.json` file records the unfinished count.

## Outputs

For separate evaluation inputs, see [Workflow 1 evaluation](fulfillment-evaluation.md).
Use `--dataset` and `--faults-file` together to select its cases and fault schedules.

- `manifest.json`: settings/code/dataset hashes, default fault definitions, trial schedule, model and budgets (no key)
- `plan.jsonl`: all scheduled slots, including those not attempted
- `trials.jsonl`: full per-trial results, each attempt's trace paths and propagation metrics
- `trials.csv`: flat summary including activation, affected/corrupted stages, unauthorized actions, wasted work, tokens and latency
- `paired.csv`: matched clean–fault differences; includes all completed and partial pairs
- `summary.json`: eligible denominators and success counts by fault class/mode
- `traces/`: raw events, prompts, artifacts and dependencies
- `spend.json`: local estimate and provider-reported usage (live mode)
- `completion.json`: attempted vs planned count, reason stopped

## Interpretation / limitations

1. `fault_activated` **must be true** and the paired clean run must pass before counting a result in a conditional fault-recovery rate. An ignored or non-activated fault is **not** a success.
2. `full_restart` is an **oracle baseline triggered by `fault_applied=true`**, with one fresh retry even if the first attempt was correct. Unapplied faults and clean runs do not trigger a restart; non-retryable errors still block retries. This assumes perfect knowledge of injection, not practical fault detection.
3. `always_verify` uses deterministic business-rule reference artifacts, a strong oracle-like simulated verifier. Describe that assumption in the report.
4. The standard ten fault templates include accidental and adversarial cases; report these groups separately. `affected_stages` records dependency reach; `corrupted_stages` records observed incorrect values. Neither alone establishes causation.
5. Workflow acts on local copies of synthetic fulfillment state; the experiment does not touch real external orders.
6. The default fault cases were used during development, so this runner is suitable for a **live pilot**, not an independent held-out evaluation without a separately prepared test set and compatible fault specifications.
7. This runner does not compute an unconditional recovery rate or infer dollars from missing token usage. `reported_total_tokens` is a lower-bound subtotal, while `total_tokens` is null whenever any call's usage is unknown.
8. `trials.jsonl` may contain raw model text and synthetic customer/order data. Treat it as potentially sensitive and avoid committing it without review.

