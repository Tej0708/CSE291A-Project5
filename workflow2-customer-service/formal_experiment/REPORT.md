# Formal QA-corruption preparation report

Preparation complete; no unresolved implementation blocker. No model/provider requests or formal experiment executions were made. No restart or always-verify logic was added.

## Deliverables

- `../formal_observer.py`: new serial observer, accurate model/tool invocation context, symmetric clean/fault Router inputs and selected/subsequent actions, linked run/event/call IDs, immediate QA-injection boundary records, provider usage with nullable totals and explicit known subtotals.
- `../run_formal_experiment.py`: offline prepare/verify/evaluate and explicitly invoked future execute command, frozen hash checks, fresh state/client per run, serial schedule, no retries, error-stop with every planned slot retained, exclusive output creation.
- `manifest.json` and `manifest.json.sha256`: dataset-derived 20 mixed cases, 40 runs, original budgets, pilot model/settings and source hashes. Seed 20261102 yields ten clean-first and ten fault-first pairs. Re-generation is byte-identical.
- `*.schema.json`: trace, raw results, metrics, paired results, draft assessment and latest-answer contracts.
- `PLAN.md`: exact validation/execution/evaluation commands, frozen evaluation procedure, denominators, limitations and remaining Phase 1 checklist.

## Offline validation

`tests.txt`: **31 tests pass**, including 26 existing workflow tests and five new formal tests. The new tests perform 160 paired plain/observed comparisons across all 40 base cases, both conditions and both scripted classification orders. They compare exact model inputs, full workflow histories/results and activation outcomes; verify invocation stages/iterations, Router receipt/action dependencies, multi-iteration mutation/repeated work, skipped single-issue injections, fresh-state isolation, restored monkeypatches, classification/helper errors, exact provider request shape, nested usage preservation and missing/zero token behavior. No provider SDK client is initialized in fixtures.

The integration fixture checks all 40 planned slots, offline extraction, paired overhead and review templates. Synthetic review labels verify that an earlier failed draft remains in all-draft counts while latest-per-issue run scoring can pass. Synthetic answers/labels are test scaffolding, not measured quality; temporary fixture artifacts are deleted by tests.

`review_tests_with_loopback.txt`: **9 existing review-tool tests pass**. The initial sandbox run (`review_tests.txt`) passed eight and could not bind the local HTTP test server; rerunning with local loopback permission passed all nine. No external/model API call was involved.

## Preservation and limits

`preservation_check.json` verifies **374 pre-existing files unchanged**, including sources, datasets, prompts/injector code, pilot raw traces, evaluations, baseline labels and evaluation rules. Pre-existing working-tree edits were not reverted. Only new preparation files were added. Credential/environment, cache, editor and Git-internal files were excluded from the content inventory.

The formal runner uses the corrected observer; historical runners and raw traces remain as recorded. Observation uses scoped global patches and therefore supports serial execution only. Provider alias/default stability and live connectivity cannot be verified offline. Provider usage may remain unavailable and is never invented. Elapsed time includes observer overhead. Partial run errors retain call and injection-boundary evidence even when no completed workflow result exists.

Formal execution awaits separate authorization. After execution, all helper drafts still require offline semantic review under the frozen rules, with provenance and separate adjudication revisions. Ledger completion, latest-answer quality and all-draft quality remain separate.
