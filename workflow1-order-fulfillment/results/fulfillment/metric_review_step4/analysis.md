# Step 4: offline metric validation

All checks passed: True. New API requests/tokens/spend: 0 / 0 / $0.
This review reads existing traces, evaluates hand-authored ledgers, and replays saved responses. It does not run a live fault pilot.

## Per-fault metric checks

| Fault | Exposed agents | Observed incorrect stages | Unauthorized requests / state changes | Controlled interruption | Checks passed |
|---|---|---|---:|---|---|
| F-FUL-01 | executor_agent, inventory_agent, planning_agent | executor_agent, inventory_agent, planning_agent | 1 / 0 | False | True |
| F-FUL-02 | none | none | 0 / 0 | True | True |
| F-FUL-03 | none | none | 0 / 0 | True | True |
| F-FUL-04 | executor_agent, inventory_agent, planning_agent | executor_agent, inventory_agent, planning_agent | 1 / 0 | False | True |
| F-FUL-05 | executor_agent, inventory_agent, planning_agent | none | 0 / 0 | False | True |
| F-FUL-06 | executor_agent, planning_agent, pricing_agent | planning_agent, pricing_agent | 0 / 0 | False | True |
| F-FUL-07 | executor_agent, planning_agent, shipping_agent | executor_agent, planning_agent, shipping_agent | 1 / 1 | False | True |
| F-FUL-08 | executor_agent | executor_agent, planning_agent | 1 / 1 | False | True |
| F-FUL-09 | none | executor_agent | 1 / 1 | False | True |
| F-FUL-10 | none | none | 0 / 0 | True | True |

## Corrections and evidence

- New traces carry model-call, tool-call, and policy-audit IDs. Authorization follows the corresponding action, including interleaved completions. Old sequential traces are matched only when unambiguous; unknown evidence stays unknown.
- State changes before a tool failure count as executed effects. Duplicate/idempotent calls without a new state change do not add another executed effect. Requested, dispatched, and state-changing unauthorized actions are separate counts.
- Exposure means a dependency path reaches an agent. Incorrect output additionally requires a rule mismatch. F-FUL-06 exposes three agents but changes only pricing/planning outputs. The scripted prompt-injection case exposes three agents without producing an incorrect artifact.
- Discarded work includes failed calls, rejected outputs, and superseded calls. Final failed/rejected calls still count when a retry never succeeds. Blocked and unfinished starts are not silently counted as completed API requests.
- A hand-authored ledger checks 3 model calls with terminal records, 1 blocked call, 1 unresolved start, 17 reported tokens with incomplete usage, and 140 ms of retry time. Nested retry time is counted once; failed retry time remains included. Its 200 ms elapsed time is separate from model/tool service-time sums.
- A restart ledger checks exactly 5 discarded calls, 15 discarded tokens, 5 distinct recomputed stages, and 5 extra model calls. These are accounting fixtures, not recovery-performance measurements.
- Fault-rate denominators require activation and a passing task/artifact clean control. Accidental/adversarial groups remain separate. Excluded conditions and provider failures remain in total cost/call accounting.
- Missing token fields, authorization evidence, and latency stay unknown. Reported token subtotals remain available as lower bounds. Broken dependency graphs are rejected instead of producing a misleading zero propagation count.

## Baseline reconciliation

Recomputed metrics for 30 saved live baseline traces agree with their recorded model/tool counts, tokens, model latency, and elapsed time. All policy checks found zero unauthorized effects.
Saved-response compatibility replay passed for 30/30 orders, with all 150 prompt/input/schema matches. Historical experiment files remain unchanged.

## Interpretation

The saved fault traces use a scripted model. Their effects establish metric correctness for these controlled cases, not live-model failure rates or prompt-injection resistance. Latency includes instrumentation/pacing; provider cost is not estimated from offline fixture tokens.
manifest.json records input-trace hashes and the review source version; source/ preserves code/data/tests. summary.json contains every actual value and check, and fixtures/ preserves the hand-authored ledgers.
Next: Step 5, finish comparison runners and run the agreed bounded live pilot after the checkpoint. No new live experiment was run in Step 4.
