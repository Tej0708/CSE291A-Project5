# Step 2: clean fulfillment baseline

Completed 30/30 attempted orders. Task correctness: 30/30. Artifact/state checker: 30/30.

One repetition on the current prompt/schema version. Earlier clean_pilot_1 results are development evidence and are not pooled with this baseline.
Every order starts from an independent copy of the fixed inventory snapshot. The gold table is used only for evaluation.

## API usage

- New API requests: 150 (limit 150).
- Reported input/output tokens: 88887 / 10820.
- Estimated charge from published rates: $0.01874305 (local limit $0.05).
- Unknown-usage calls: 0. Conservative reservations remain separate from measured charges.
- Provider key spend before/after: 0.0122451 / 0.02986390000000001. The change is key-wide and can include other concurrent use.
- Published prices and provider usage snapshots are saved in spend.json. Local estimates are not a substitute for provider billing.
- Requests are paced, SDK retries are disabled, and each response is capped at 1,024 completion tokens.

## Per-order results

| Order | Task correct | Checker passed | Outcome | Calls | Tokens | End-to-end ms |
|---|---|---|---|---:|---:|---:|
| ORD-1001 | True | True | fulfilled | 5 | 3221 | 5520.66 |
| ORD-1002 | True | True | rejected_insufficient_stock | 5 | 3197 | 4511.58 |
| ORD-1003 | True | True | fulfilled | 5 | 3562 | 6127.22 |
| ORD-1004 | True | True | rejected_insufficient_stock | 5 | 3135 | 4506.22 |
| ORD-1005 | True | True | fulfilled | 5 | 3291 | 5172.89 |
| ORD-1006 | True | True | rejected_insufficient_stock | 5 | 3141 | 4928.40 |
| ORD-1007 | True | True | fulfilled | 5 | 3579 | 5301.04 |
| ORD-1008 | True | True | fulfilled | 5 | 3290 | 4785.56 |
| ORD-1009 | True | True | rejected_insufficient_stock | 5 | 3135 | 5273.79 |
| ORD-1010 | True | True | fulfilled | 5 | 3232 | 4991.39 |
| ORD-1011 | True | True | fulfilled | 5 | 3614 | 4794.63 |
| ORD-1012 | True | True | fulfilled | 5 | 3234 | 5004.51 |
| ORD-1013 | True | True | rejected_insufficient_stock | 5 | 3419 | 4910.86 |
| ORD-1014 | True | True | fulfilled | 5 | 3294 | 5479.68 |
| ORD-1015 | True | True | rejected_insufficient_stock | 5 | 3484 | 4833.66 |
| ORD-1016 | True | True | fulfilled | 5 | 3239 | 5359.11 |
| ORD-1017 | True | True | rejected_insufficient_stock | 5 | 3147 | 4869.58 |
| ORD-1018 | True | True | fulfilled | 5 | 3563 | 4942.00 |
| ORD-1019 | True | True | rejected_insufficient_stock | 5 | 3137 | 4892.70 |
| ORD-1020 | True | True | fulfilled | 5 | 3275 | 5999.77 |
| ORD-1021 | True | True | rejected_insufficient_stock | 5 | 3139 | 4303.48 |
| ORD-1022 | True | True | fulfilled | 5 | 3562 | 9922.98 |
| ORD-1023 | True | True | fulfilled | 5 | 3292 | 5119.69 |
| ORD-1024 | True | True | rejected_insufficient_stock | 5 | 3135 | 4821.81 |
| ORD-1025 | True | True | fulfilled | 5 | 3247 | 5105.77 |
| ORD-1026 | True | True | fulfilled | 5 | 3626 | 5034.14 |
| ORD-1027 | True | True | fulfilled | 5 | 3269 | 5091.35 |
| ORD-1028 | True | True | rejected_insufficient_stock | 5 | 3480 | 10488.82 |
| ORD-1029 | True | True | fulfilled | 5 | 3304 | 6017.34 |
| ORD-1030 | True | True | rejected_insufficient_stock | 5 | 3464 | 5355.47 |

## Interpretation

This is a pilot over 30 synthetic cases, not an estimate of reliability across arbitrary orders or repeated stochastic runs. End-to-end latency includes pacing and logging; model-call latency is recorded separately in runs.jsonl.
manifest.json fixes source hashes, model settings, package versions, dataset, and spending limits. source/ preserves the executed code/data without credentials. traces/ contains every input, raw response, artifact, dependency, action, and terminal result.
Next recommended step: review the existing fault-injection harness and confirm controlled activation/consumption before any live fault experiment. No fault/recovery matrix is part of this baseline step.

## Follow-up verification

All 30 unique orders passed task and artifact/state checks: 18 fulfilled and 12 rejected for
insufficient stock. There were 150 successful model calls, 186 tool calls, and no fault
injections or retries. All 35 saved source/data files match the manifest hashes. See
`verification.json` for the saved checks and aggregate latency.

The immediate post-run billing snapshot had not yet counted every request. A read-only
follow-up at 2026-11-02 06:25:05 UTC reported cumulative key spending of $0.03098815. Compared
with $0.01224510 before the run, the increase is $0.01874305, matching the published-rate
estimate. Remaining balance against the $50 key budget: $49.96901185. This is key-wide
spending; concurrent use could affect future snapshots. Raw snapshots remain saved in
`spend.json` and `key_usage_followup.json`.

Offline tests: 33 passed. Step 2 is complete; further Phase 1 work is paused at the requested
checkpoint. See [progress and usage ledger](../../../docs/phase1-progress.md).
