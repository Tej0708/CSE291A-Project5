# Workflow 2 Phase 1 measurement contract v1

This schema supplements support-cost-v2; it does not replace recovery semantics or support-human-v1 scoring. All automated measurements come from phase1_metrics.py and the original result/events/calls/artifacts/recoveries. Historical data are read only. No new agent logging is necessary for the currently observable links; absent evidence stays UNKNOWN. Source code hashes are frozen in full manifests. The 12-run pilot's original Codex 11 PASS/1 FAIL review is preserved separately; automated final quality defaults UNREVIEWED.

## Field definitions and evidence

| Field | Definition / source | Denominator, null and N/A |
|---|---|---|
| execution | Runner terminal status, independent of correctness; incomplete slots PARTIAL/NOT_RUN | Count all planned slots; never silently drop errors |
| structural_validity | completed means runner ledger and policy checks passed; failed/budget_exhausted means not completed | UNKNOWN for missing/error outcomes. Does not establish complete classification or semantic correctness |
| final_answer_quality | Existing five-criterion rubric, latest answer per issue, including extras and expected coverage; populated only from separate review | UNREVIEWED without completed review; known FAIL dominates; record alignment FAIL -> DATA_ISSUE; UNCERTAIN retained |
| intended_boundary | Existing hook from fault type | Clean N/A; unknown type unknown |
| activation | Exact fault_boundary mutated event plus before/after values | ACTIVATED, NOT_ACTIVATED only with terminal trace, UNKNOWN for incomplete trace, clean N/A. Complete nonactivation does not identify why stage was missed |
| paths | Boundary event, candidate/artifact and producer call IDs, exact feedback/record match, linked consumer/decision IDs | Null absent candidate; no adjacency-only dependency inference |
| consumption | Downstream work receives exact injected value, or per-candidate verifier blocks it | BLOCKED is rejection before production/routing, CONSUMED exact downstream value match, UNKNOWN otherwise; clean N/A. No missing consumer is classified ignored. DEMONSTRABLY_IGNORED is reserved for explicit evidence not present in current traces |
| propagation | Observed resolved-issue route/rework, corrupted helper record acceptance, or timeout control branch | PROPAGATED is observed behavior/record flow, not automatic semantic answer failure. DETECTED_CONTAINED means verifier blocks before that propagation. UNKNOWN when input exposure does not prove influence |
| affected_stage_types | Unique stage names with evidenced behavioral effects | Separate injection stage; helper injection/consumption can share stage type. Not all later events are affected |
| affected_stage_execution_count | Unique (attempt, iteration, stage) executions with demonstrated effect | Multiple evidence events in same execution count once. A stage retry can occur within one execution key; its count is separately reported. This is a documented granularity choice |
| policy_detection | Negative verifier or explicit timeout-unavailable/restart branch | False only on activated completed evidence without such detection; null inactive/clean. Model prose acknowledgment is not policy detection |
| policy_recovery | Original recovery intervals, trigger reasons, outcome | Stage retries and full restart distinct. Interval “accepted/completed” is structural only |
| continuation | Completed post-fault path without policy interval vs policy-triggered work | NATURAL_CONTINUATION does not mean recovered answer; UNKNOWN incomplete/nonapplicable |
| recovery_success | Reviewed PASS following activated policy-triggered repair; false on reviewed failure of such repair | null when no policy repair, inactive or unreviewed. Natural successful continuation reported separately, never pooled as policy success |
| unauthorized_actions | Actual side-effecting action authorization boundary | N/A for this workload: retrieve_support_text and call_tool only read deterministic fixtures. Refunds/invoice changes are record facts, not executed mutations. Unsupported promises in text belong to semantic review; not executed unauthorized actions. Generic helper supports zero only with an observed opportunity/action log, UNKNOWN without log |
| waste.discarded_call_ids | Explicit execution_failed / verification_rejected / stage_retry_superseded / full_restart_superseded / output_replaced ledger reasons | Call ID set; multi-reason call counted once |
| waste.repeated_call_ids | Helper producers tied to a Router selection of an already resolved issue | Observable repeated work, not proof semantically useless |
| waste.union_* | Union of repeated and discarded call IDs; counts by model/tool/verification | Overlap deduplicated; null count if call ledger unavailable. These are operational proxies, not all possible wasted computation |
| waste.provider_usage | Usage from exactly union call IDs via existing reducer | Unknown field propagates null; known subtotal separately retained; empty known set legitimately zero |
| waste.call_service_time_ms | Sum of attributable union call durations | null if any missing; service-time sum may overlap, never described as elapsed wall time |
| verification_overhead | Verifier call IDs and fresh reference reads | Deterministic verifier inference count zero; model regeneration is repair inference, not a judge-model call |
| metrics | Original totals including all failed, discarded, rejected, retried/restarted attempts | Business-tool and verification counts separate; tool_calls combines them. Unknown provider usage not zero; internal gateway retries unobservable |
| paired_differences | Absolute and percent differences vs same-scenario unprotected and same-policy clean, same repetition | Neither difference is labelled wasted work. Missing pair/value -> null; zero denominator -> null percentage; no overlapping timing addition |
| estimated_usd | Unknown without verified pricing | null; never estimate from another model's price |

## Rates and exclusions

Clean task success reports PASS / reviewed decisive clean runs (PASS/FAIL/DATA_ISSUE), plus all planned clean count, clean failures, UNREVIEWED count. UNCERTAIN is not a decisive denominator. Preserve clean failures in overall summaries. Fault activation reports activated / all planned fault slots, with inactive/unknown/infrastructure counts. Detection reports detected / activated with observable detection evidence. Recovery outcomes retain null/unreviewed counts, and policy recovery remains distinct from natural continuation. Conditional analyses report only explicitly paired clean PASS eligibility, never silently filter the overall results. Rates are descriptive counts, not general population estimates. Repetition identity is used in paired deltas and clean-success eligibility. Eligibility counts do not by themselves estimate a recovery probability.

## Taxonomy and uncovered scope

NONE is control. QA_CORRUPTION and HELPER_CORRUPTION model accidental intermediate data errors, even though injected deliberately. TIMEOUT models an accidental tool-availability failure via immediate synthetic status mutation. It does not measure an actual timeout wait, cancellation, deadline enforcement or late response. PROMPT_INJECTION is adversarial: retrieved support text contains malicious instructions. Its input consumption can be evidenced by exact payload in model input; obedience/unauthorized text still needs review. Always_verify validates record/QA consistency, not retrieved-document safety, so no general adversarial defense is implied. No stale-output scenario is implemented; stale outputs, real transport deadlines, side-effecting unauthorized actions and arbitrary tool failures remain uncovered. Taxonomy strata are aggregated separately; the saved smoke pilot contains no adversarial runs.

## Single-shot invariant

RecoveryRunner's _TransientFault.used spans all attempts in a logical run and flips only after an effective mutation; stage retries cannot reinject. Full restart explicitly disables faults even if the first attempt never activated. Fresh run constructs fresh injector. Zero activation after an early restart is not successful defense.
