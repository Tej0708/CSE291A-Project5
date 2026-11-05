# Requirements → implementation / evidence

| Requirement | Existing evidence reused | Addition / limitation |
|---|---|---|
| Controlled faults, single shot | _TransientFault.used, fault_boundary, restart disable | test_single_shot_all_faults_all_policies covers all dataset mechanisms across policies; no payload change |
| Messages, intermediate artifacts, actions/dependencies | calls.inputs/output, artifacts.source_call_ids, candidate IDs, verifier parent IDs | paths join exact payload + attempt/iteration + artifact IDs; unknown instead of adjacency-only proof |
| Activation/consumption/ignored | boundary before/after; router_selection input; helper_candidate | measure(): BLOCKED/CONSUMED/UNKNOWN/N/A; no unsupported ignored labels |
| Failure propagation | Router target/revisit, helper acceptance, timeout branches | paths, distinct stage types/execution keys; model exposure not equated to behavior |
| Unauthorized actions | Fixed simulated read-only services | N/A with contract rationale; zero/unknown helper tested; prose claims kept in review |
| Wasted work | Explicit discard reasons and producer IDs | union of discarded/repeated calls, nullable tokens/service time; useful repair/verifier IDs separate |
| Extra verification inference | Deterministic verifiers, counted references | Zero direct verifier model calls; retry inference retained in total/repair |
| Paired overhead | Complete per-run metrics | Two separately labeled same-repetition comparisons with zero/null denominator handling |
| Clean task success / recovery | Structural status, retained answers, support-human-v1 | Review adapter; no automatic semantic success; explicit rates/exclusions/clean failures |
| Accidental / adversarial | 4 accidental/control variants plus prompt injection | Static applicability all 200 variants; separate taxonomy summaries; stale/real-deadline categories uncovered |
| Full restart / always_verify | Existing RecoveryRunner | Reused unchanged through execute_one; failure trigger semantics unchanged |
| Dataset validation | Unique40 file, scenario_for, taxonomy, iteration configs | 200 variants / 40 bases; 180 statically applicable, 20 QA-inapplicable; contract checks not semantic review |
| Full experiment schedule | QA-only 40-run freeze and recovery 12-run smoke | Finalized full_config.json and full_manifest.json: 20 eligible cases, four scenarios, three policies, one execution, seed 42 |
| Immutable manifest | Existing saved settings and source hashes | Canonical manifest identity, source/data drift checks, exclusive creation |
| Safe resume | Per-run result and flushed journals | Completion receipt identity/hash, partial-run refusal, optional cumulative request budget, exclusive process lock |
| Post-run human review | Existing strict rubric, historical adjudications | Blank per-draft criteria/provenance export; new output aggregation, answer-hash validation |
| Preserve historical failure | Original analysis/codex_reviews.json and run 07 | New analysis_phase1_v3; no reinterpretation as human review or overwriting of 11/1 labels |
| No live execution | Mock SDK, blocked sockets | Tests only; no execute CLI invoked against provider |

READY TO EXECUTE: finalized 240-run schedule. Human review remains post-run. See README.md and selected_population.json for population limitations, overlap, settings and resume semantics. Historical snapshots retain their original unresolved design state.
