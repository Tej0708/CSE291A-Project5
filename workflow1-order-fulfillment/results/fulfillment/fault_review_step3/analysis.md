# Step 3: offline fault-injection review

Boundary checks passed for 10/10 schedules.
No Triton calls, credentials, or network access. Scripted outputs are not live-model robustness results.

| Fault | Class | Boundary observed | Evidence | Scripted task correct |
|---|---|---|---|---|
| F-FUL-01 | accidental | inventory_agent | changed_result_with_task_impact | False |
| F-FUL-02 | accidental | get_inventory_inputs | controlled_interruption | False |
| F-FUL-03 | accidental | get_inventory_inputs | controlled_interruption | False |
| F-FUL-04 | accidental | inventory_agent | changed_result_with_task_impact | False |
| F-FUL-05 | adversarial | inventory_agent | payload_delivery_only | True |
| F-FUL-06 | accidental | pricing_agent | changed_result_with_task_impact | False |
| F-FUL-07 | accidental | shipping_agent | changed_result_with_task_impact | False |
| F-FUL-08 | accidental | executor_agent | changed_result_with_task_impact | False |
| F-FUL-09 | accidental | update_order_status | changed_result_with_task_impact | False |
| F-FUL-10 | accidental | create_shipment | controlled_interruption | False |

## What changed

- Invalid stage/surface combinations, unsupported tool-call mutations, invalid paths, and no-op changes are rejected. Failed configuration is never marked as an injected fault or scored as a recovery trial.
- F-FUL-08 now changes shipping_usd to 0 and total_usd to the $25 subtotal. The executor consumes the shipping field and writes the wrong shipment cost. The previous total-only change affected the quote but not downstream actions.
- F-FUL-04 explicitly records a synthetic historical stock value of 5 alongside the old timestamp. It is an augmented stale-snapshot scenario, not observed historical inventory. The original workbook/JSON is unchanged.

## Evidence and controls

- Three paired clean controls establish successful execution for ORD-1001, ORD-1002, and ORD-1003. summary.json records exact fault and consumer event IDs, payload equality, dependency resolution, and all checks.
- Malformed JSON and the early timeout stop at the inventory tool boundary before an agent receives data. The late timeout occurs after inventory reservation and before shipment creation. These are controlled interruptions, not semantic propagation.
- Both timeout schedules retain the configured 1,500 ms delay in this saved review. Fast unit tests may explicitly replace that delay with zero.
- Prompt injection reaches the scripted inventory input unchanged. The scripted model ignores text instructions by construction; its correct result does not demonstrate that the live model resists the attack.
- Timestamp-only control: the old timestamp is delivered, but all artifacts and task outcome remain correct. This demonstrates why the stale scenario needs an explicitly declared stock-value change.
- Total-only planner control: the incorrect quote reaches the executor, but executor actions and business state remain unchanged. Delivery alone is not proof of downstream behavioral dependence.
- Saved-response compatibility replay: 30/30 orders passed. All 150 prompts, input payloads, and schemas matched the Step 2 requests exactly; final business states also matched. No baseline rerun was billed.
- Original clean-baseline artifacts remain unchanged. manifest.json and source/ preserve this review version, including tests. Fault values and schedules are saved separately from dataset.json.

## Limits and next checkpoint

The nine accidental scenarios demonstrate task failures under the scripted model; the adversarial scenario demonstrates delivery only. The actual live fault pilot and recovery comparisons remain pending. This review does not estimate live failure rates or validate the propagation/wasted-work metrics.
Next: Step 4, offline validation of propagation and policy-violation metrics. No live experiment is part of that checkpoint.

Reproduce with `python -m experiments.review_faults --output-dir <new-directory> --baseline-dir results/fulfillment/clean_baseline_step2`.
