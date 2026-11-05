# Workflow 1 evaluation dataset

`data/fulfillment_eval.json` contains 30 new synthetic orders, 60 new products,
six shipping rates, inventory records, and independently calculated ground truth.
The original `data/dataset.json` is unchanged. Each run starts with fresh state.

| Cases | Expected decision | Count |
|---|---|---:|
| EVAL-2001–2010 | Approve fulfillment | 10 |
| EVAL-2011–2020 | Reject insufficient stock | 10 |
| EVAL-2021–2030 | Reject shipping constraint | 10 |

Cases vary one to three line items, quantities, purchase prices that differ from
catalog prices, fractional weights, local/regional/national zones, and
standard/express services. EVAL-2001 requires exactly the available stock;
EVAL-2002 weighs exactly 10 kg; EVAL-2011 is one unit short; EVAL-2021 weighs
10.25 kg against a 10 kg limit. Existing reservations are nonzero in some cases.
Ground truth uses decimal arithmetic with half-up rounding to cents, stock
rejection before shipping rejection, and null shipping/total for rejections.
Only the checker reads ground truth; agents receive operational records.

`data/fulfillment_eval_faults.json` defines E-FUL-01 through E-FUL-10 on ten
distinct orders. These cover incorrect inventory, malformed output, early
timeout, stale inventory, adversarial instructions, wrong pricing, wrong shipping,
corrupted plans, unauthorized executor actions, and a late shipment timeout.
The stale case supplies declared synthetic historical stock, not a timestamp-only
mutation. Nine cases are accidental and one is adversarial.

Run the paired matrix offline with Python 3.10 or newer:

```bash
python -m experiments.run_live_fault_recovery --scripted \
  --dataset data/fulfillment_eval.json \
  --faults-file data/fulfillment_eval_faults.json \
  --output-dir results/fulfillment/eval_smoke_01
```

This runs 60 trials across the ten fault cases and three modes. Each clean
control uses the same case and mode as its paired fault trial. It does not run
the other 20 clean cases; the automated dataset tests exercise all 30 cases
under all three modes:

```bash
python -m pytest tests/test_eval_dataset.py -q
```

For a small live pilot, omit `--scripted` and select a case with explicit limits:

```bash
python -m experiments.run_live_fault_recovery \
  --dataset data/fulfillment_eval.json \
  --faults-file data/fulfillment_eval_faults.json \
  --fault-id E-FUL-01 --max-api-calls 75 --max-cost-usd 0.10 \
  --output-dir results/fulfillment/eval_live_01
```

Use a new output directory each time. The manifest preserves the selected
dataset hash and full selected fault definitions. Full restart uses oracle
injection knowledge; always verify uses deterministic reference checks.

These are separate inputs validated with scripted models, using the same task
rules and fault families as development. They are not an independent real-world
benchmark, and scripted tests do not establish live-model robustness. Freeze
the dataset before live evaluation and avoid tuning prompts to its results if
you intend to report it as held-out evaluation. No live results are supplied.
