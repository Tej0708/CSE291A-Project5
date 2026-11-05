# Fulfillment Live Recovery Evaluation — Verified Analysis

Experiment directory: `/Users/nkris/Desktop/UCSD/CSE291A-Project5/results/fulfillment/eval_live_final_r3`

Automatically generated from experiment outputs

## 1. Experiment integrity and accounting

| Measure | Verified value |
| --- | --- |
| Planned / attempted slots | 180 / 180 |
| Experiment complete | YES |
| Stop reason | None |
| Clean controls fully correct | 90 / 90 |
| Faults activated | 90 / 90 |
| Faults meaningfully exercised | 90 / 90 |
| API calls: trial sum / spend.json | 1008 / 1008 |
| Input tokens: trial sum / spend.json | 649659 / 649659 |
| Output tokens: trial sum / spend.json | 102676 / 102676 |
| Unknown-usage calls | 0 |
| Incomplete model/tool/verification calls | 0 / 0 / 0 |
| Workflow attempts / raw trace files | 210 / 210 |
| Estimated experiment cost | $0.148787 |
| Cross-file accounting errors | 0 |


Cross-file validation passed for the checked fields in `trials.jsonl`, `trials.csv`, `paired.csv`, `plan.jsonl`, `summary.json`, `completion.json`, `spend.json`, and raw trace counts.

## 2. Final correctness by fault class

`Final correct` = completed run + task check passed + independent checker passed. Accidental and adversarial faults are kept separate.

| Fault class | Mode | Eligible n | Final correct | Rate |
| --- | --- | --- | --- | --- |
| accidental | unprotected | 27 | 0/27 | 0.0% |
| accidental | full_restart | 27 | 27/27 | 100.0% |
| accidental | always_verify | 27 | 24/27 | 88.9% |
| adversarial | unprotected | 3 | 3/3 | 100.0% |
| adversarial | full_restart | 3 | 3/3 | 100.0% |
| adversarial | always_verify | 3 | 3/3 | 100.0% |


The adversarial results come from one distinct fault schedule; `Eligible n` shows the number of repetitions included per mode.

## 3. Fault propagation, affected stages, and policy-invalid actions

`Affected stages` counts dependency-affected stages; `corrupted stages` counts stages independently observed as wrong. `Downstream corruption` means corruption reached a later stage. Action columns are total action counts, not percentages.

| Class | Mode | n | Fault exercised | Agent exposure | Downstream corruption | Mean affected stages | Mean corrupted stages | Controlled interruption | Policy-invalid attempts | Policy-invalid executed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accidental | unprotected | 27 | 100.0% | 55.6% | 55.6% | 1.67 | 1.56 | 33.3% | 15 | 9 |
| accidental | full_restart | 27 | 100.0% | 55.6% | 55.6% | 1.67 | 1.56 | 33.3% | 15 | 9 |
| accidental | always_verify | 27 | 100.0% | 44.4% | 0.0% | 0.67 | 0.67 | 33.3% | 0 | 0 |
| adversarial | unprotected | 3 | 100.0% | 100.0% | 0.0% | 3.00 | 0.00 | 0.0% | 0 | 0 |
| adversarial | full_restart | 3 | 100.0% | 100.0% | 0.0% | 3.00 | 0.00 | 0.0% | 0 | 0 |
| adversarial | always_verify | 3 | 100.0% | 100.0% | 0.0% | 3.00 | 0.00 | 0.0% | 0 | 0 |


A fault can be meaningful without downstream-agent exposure: verification may stop it first, a timeout may interrupt execution, or an Executor-stage fault may affect tools with no later agent.

## 4. Fault-run resource effect relative to matched clean controls

Each row uses matched pairs from the same case, mode, and repetition. `ΔX = X_fault − X_clean`; the reported value is the mean ± SD of those pairwise differences. Positive means the fault run used more; negative means it used less (for example, because execution stopped early).

| Class | Mode | Matched n | Δ model calls | Δ total tools | Δ verification | Δ tokens | Δ E2E ms | Δ est. cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accidental | unprotected | 27 | -1.11 ± 2.12 | -0.78 ± 1.25 | 0.00 ± 0.00 | -845.3 ± 1688.4 | -729.0 ± 2005.0 | $-0.000159 |
| accidental | full_restart | 27 | 3.89 ± 2.12 | 5.11 ± 1.89 | 0.00 ± 0.00 | 2956.9 ± 1627.8 | 5383.2 ± 5457.4 | $0.000598 |
| accidental | always_verify | 27 | 0.67 ± 0.48 | 1.44 ± 0.97 | 0.67 ± 0.48 | 471.5 ± 374.8 | 1039.0 ± 860.9 | $0.000093 |
| adversarial | unprotected | 3 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 30.0 ± 2.0 | -54.9 ± 327.6 | $0.000005 |
| adversarial | full_restart | 3 | 5.00 ± 0.00 | 5.00 ± 0.00 | 0.00 ± 0.00 | 3209.3 ± 1.2 | 4943.6 ± 208.8 | $0.000576 |
| adversarial | always_verify | 3 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.0 ± 2.0 | 264.4 ± 323.0 | $0.000004 |


`tool_calls` uses the experiment's agreed definition and includes verification calls.

### Recovery work / wasted work

Work-count values are averages over eligible fault runs. `Recomputed stages` counts stage types executed more than once in a logical trial. `Discarded` calls are failed, rejected, or superseded calls that did not contribute usable final work. Recovery latency is averaged only across runs that actually recorded recovery work (>0 ms).

| Class | Mode | n | Recomputed stages | Recomputed model calls | Discarded model calls | Discarded tokens | Runs with recovery work | Recovery latency ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| accidental | unprotected | 27 | 0.00 | 0.00 | 0.00 | 0.0 | 0 | N/A |
| accidental | full_restart | 27 | 3.89 | 3.89 | 3.89 | 2954.1 | 27 | 5011.2 |
| accidental | always_verify | 27 | 0.67 | 0.67 | 0.67 | 471.2 | 24 | 964.9 |
| adversarial | unprotected | 3 | 0.00 | 0.00 | 0.00 | 0.0 | 0 | N/A |
| adversarial | full_restart | 3 | 5.00 | 5.00 | 5.00 | 3210.0 | 3 | 5009.9 |
| adversarial | always_verify | 3 | 0.00 | 0.00 | 0.00 | 0.0 | 0 | N/A |


## 5. Per-fault final correctness

Each cell shows successful final-correct fault runs / eligible repetitions for that fault × mode.

| Fault | Type | Class | Stage | Unprotected | Full restart | Always verify |
| --- | --- | --- | --- | --- | --- | --- |
| E-FUL-01 | incorrect_result | accidental | inventory_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-02 | malformed_json | accidental | inventory_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-03 | timeout | accidental | inventory_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-04 | stale_result | accidental | inventory_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-05 | prompt_injection | adversarial | inventory_agent | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-06 | incorrect_result | accidental | pricing_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-07 | incorrect_result | accidental | shipping_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-08 | incorrect_result | accidental | planning_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-09 | incorrect_result | accidental | executor_agent | 0/3 (0.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| E-FUL-10 | timeout | accidental | create_shipment | 0/3 (0.0%) | 3/3 (100.0%) | 0/3 (0.0%) |


## 6. Clean-mode cost and overhead

Absolute values below are averages over the clean runs recorded for each mode; `n` shows the denominator.

| Mode | n | Model calls | Total tools | Verification | Non-verif tools | Tokens | E2E ms | Verification latency ms | Est. cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unprotected | 30 | 5.00 | 5.80 | 0.00 | 5.80 | 3737.9 | 5067.2 | 0.00 | $0.000737 |
| full_restart | 30 | 5.00 | 5.80 | 0.00 | 5.80 | 3737.3 | 5133.3 | 0.00 | $0.000737 |
| always_verify | 30 | 5.00 | 10.80 | 5.00 | 5.80 | 3737.9 | 5248.5 | 2.62 | $0.000737 |


For matched clean overhead, `ΔX = X_clean_mode − X_unprotected_clean` on the same case/repetition. Small token/latency differences can be normal live-call variability when call counts are unchanged.

| Mode vs unprotected | Matched n | Δ model | Δ total tools | Δ verification | Δ non-verif tools | Δ tokens mean±SD | Δ E2E mean±SD ms | Δ est. cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_restart | 30 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | -0.6 ± 24.7 (median 0.0) | 66.1 ± 780.1 (median 151.6) | $0.000000 |
| always_verify | 30 | 0.00 ± 0.00 | 5.00 ± 0.00 | 5.00 ± 0.00 | 0.00 ± 0.00 | 0.0 ± 20.8 (median 1.0) | 181.3 ± 1201.0 (median 0.3) | $0.000000 |


## 7. Repetition consistency

Final-correctness outcomes were consistent across all **30** fault×mode groups (3 eligible repetitions per group).

`variability.csv` contains per-fault×mode means and SDs for resource/recovery measurements.

## 8. Review outcomes

| Review label | Fault | Mode | Count | Reps | Category | Rule-based reason |
| --- | --- | --- | --- | --- | --- | --- |
| NOTE | E-FUL-05 | unprotected | 3 | 1,2,3 | unprotected_final_correct_no_observed_corruption | Unprotected run was final-correct after an activated fault; no corrupted stage was observed. |
| REVIEW | E-FUL-07 | full_restart | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-07 | unprotected | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-08 | full_restart | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-08 | unprotected | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-09 | full_restart | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-09 | unprotected | 3 | 1,2,3 | policy_invalid_action_executed | 1 policy-invalid action(s) changed simulated state before recovery/finalization. |
| REVIEW | E-FUL-10 | always_verify | 3 | 1,2,3 | recovery_failed | always_verify did not recover final correctness. |


These are rule-based review flags, not automatic exclusions.

## 9. Timing notes

| Review label | Fault | Mode | Count | Reps | Rule-based reason |
| --- | --- | --- | --- | --- | --- |
| NOTE | E-FUL-06 | full_restart | 1 | 3 | E2E latency 35348.8 ms is >3× the full_restart/fault median (10105.1 ms). |


## 10. Generated files

- `summary.md` — human-facing verified report; start here.
- `by_mode.csv` — pooled mode metrics for secondary/descriptive use.
- `by_class_and_mode.csv` — class-separated correctness, propagation, resource, and recovery metrics.
- `by_fault.csv` — one row per fault.
- `by_mode_and_fault.csv` — detailed fault × mode measurements across repetitions.
- `clean_metrics.csv` / `clean_overhead.csv` — clean-run cost and matched overhead.
- `variability.csv` — repetition variability by fault × mode.
- `integrity_issues.csv` — experiment/accounting issues only.
- `notable_outcomes*.csv` — rule-based outcome review flags.
- `review_queue.csv` — integrity + outcome review rows.
- `analysis.json` — machine-readable analysis.

Raw JSONL traces remain the underlying audit evidence.
