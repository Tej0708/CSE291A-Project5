# Workflow 2 team handoff — logging schema and metrics

Updated 2026-11-02. Formal experiment preparation is complete and offline-validated; live formal execution is still pending authorization. The authoritative plan is [formal_experiment/PLAN.md](formal_experiment/PLAN.md). The realized 40-run schedule and content hashes are in [manifest.json](formal_experiment/manifest.json).

## Logging contract: read these files first

1. [event.schema.json](formal_experiment/event.schema.json) defines shared JSONL fields. Read `Observer.emit`, `scope`, `complete` and `run` in [formal_observer.py](formal_observer.py) for the event-specific payloads and actual observation boundaries.
2. [result.schema.json](formal_experiment/result.schema.json) defines the saved `result.json` envelope; the observer implementation supplies the nested audit events, drafts, snapshots and provider usage. Schemas are extensible and do not exhaustively type every nested/provider-specific field; use implementation plus fixtures when integrating.
3. [test_formal_experiment.py](test_formal_experiment.py) verifies the contract against unchanged workflow requests/results, both conditions, issue order, repeated iterations, skips, errors and fresh-run isolation. Tests use scripted answers, not model-quality evidence.

Every event carries `run_id`, `event_id`, `stage`, `iteration`, `issue`, elapsed time and `depends_on`. `previous_event_id` gives serialization order; dependency IDs express workflow relationships. Model/tool requests and their result/error events share `call_id`. Classification is iteration 0; helper/tool/model calls carry the active helper stage and actual loop iteration. There is no model invocation for deterministic Router selection.

The main event chain is QA feedback → `router_input` → `router_selection` → `helper_start` → `tool_request`/`tool_result` → `model_request`/`model_result` → `helper_end`. `workflow_action` records route/no-helper and other workflow actions. `qa_injection_boundary` records pre/post feedback immediately, while `injection_audit` links the existing audit's consumption evidence after completion. Read actual `depends_on` fields; not every adjacent event has a direct causal relationship. Both clean and fault runs record actual Router receipt and ledger state.

Provider `usage` is retained without dropping nested fields. `provider_tokens` has `total`, `known_subtotal` and `missing_calls` for each token type. Null means unavailable; zero means observed zero (or no calls). Never coerce missing usage to zero. Runtime errors may leave partial calls/injection observations without a completed workflow result.

Use this new observer for formal runs. Historical pilot/baseline traces and their older context labels remain immutable; do not silently retrofit them to the new schema. Global observation patches require serial execution.

## Metrics contract: schemas plus executable definitions

Read [metrics.schema.json](formal_experiment/metrics.schema.json) and [paired_result.schema.json](formal_experiment/paired_result.schema.json), then **`evaluate()` in [run_formal_experiment.py](run_formal_experiment.py)**. That function is the executable definition of derived outputs, rather than the legacy pilot summaries.

| Output / field | Meaning and alignment requirement |
| --- | --- |
| `metrics.json`: `eligibility`, `skip_reasons`, `mutation_count` | Keep eligibility, actual mutation and non-activation reasons separate. Clean eligibility is null/not applicable. Unknown partial-error values remain unknown. |
| `router_receipt` | Existing audit's effective mutated feedback consumption; inspect linked raw events for the exact received value. |
| `repeated_helper_calls`, `repeated_tool_calls` | Actions linked to Router selections of an already ledger-resolved issue. Do not infer tool counts from successful helper outputs. |
| `affected_stages` | Observed stages after the first mutation; temporal reach, not automatic causal attribution. Use linked repeated-work evidence and clean comparison for causal discussion. |
| `subsequent_unresolved_work` | Later Router selections of issues genuinely unresolved at receipt. Continuation is not full restart or semantic recovery. |
| `ledger_completion` | Control-flow/evidence status only; not answer correctness or verified customer-side repair. |
| `iterations`, `model_calls`, `tool_calls`, `provider_tokens`, `elapsed_seconds`, `error_type` | Measured overhead and errors. Elapsed time includes observation overhead. Keep missing usage explicit. |
| `paired_results.json`: `deltas` | Fault minus clean for completed pairs. Missing usage/incomplete pairs produce null deltas. Preserve all 20 planned pairs. |

Report the full 20 planned fault slots and 40 total slots, then attempted/completed/eligible/mutated/consumed/repeated counts and skips separately. No skipped case is a successful defense; no replacement after outcomes. Do not combine pilot and formal results.

## Quality contract: three separate views

The frozen interpretation is [BASELINE_EVALUATION_RULES.md](BASELINE_EVALUATION_RULES.md), with original rubric and provenance links. Read [draft_assessment.schema.json](formal_experiment/draft_assessment.schema.json), [latest_answer_quality.schema.json](formal_experiment/latest_answer_quality.schema.json), and `aggregate`/`summarize` in [human_review_tool/review_app.py](human_review_tool/review_app.py).

- Ledger status stays in structural metrics.
- `all_draft_quality.json` retains every helper attempt, including superseded failures. `quality_summary.json` reports helper-level statistics separately.
- `latest_answer_quality.json` scores the latest answer per issue, including extras, with expected coverage/completion and record-alignment handling. It is not just the final message. There is no final-answer composition agent.

`assessment_template.json` starts UNREVIEWED; fill a separate assessments file with reviewer/provenance, criterion scores, quotes, rule references and reasons. The evaluator aggregates supplied judgments offline; it does not automatically judge prose. Record-alignment failure is DATA_ISSUE. Unsupported refund timing/destination and unsupported definite repair claims follow the documented frozen rules. Preliminary Codex labels must not become human-finalized labels by renaming them.

## How to coordinate changes and next work

1. Agree on field semantics using the schema/implementation/test mapping above. Add downstream adapters in separate files if needed.
2. Run `run_formal_experiment.py verify` before any authorized live execution. The manifest hashes observer, evaluator, tests, schemas, rules and workflow inputs; editing a frozen file intentionally makes verification fail.
3. If a contract change is necessary, propose a new version and revalidate/re-freeze into a separate manifest. Do not overwrite this freeze, modify historical traces, or silently update hashes merely to pass verification.
4. After authorization, execute serially into a new `results/workflow2_formal_*` directory, then run offline evaluation and independent draft review using the commands in [PLAN.md](formal_experiment/PLAN.md).
5. Publish activation/overhead and the three separate quality/control views. Restart and always-verify remain later work with their own protocol and matching baseline.

Preparation evidence: [REPORT.md](formal_experiment/REPORT.md), [31 workflow tests](formal_experiment/tests.txt), [9 review-tool tests](formal_experiment/review_tests_with_loopback.txt), [preservation check](formal_experiment/preservation_check.json). The initial review HTTP test was sandbox-blocked; all nine passed after local loopback permission. No model/provider calls were made during preparation.
