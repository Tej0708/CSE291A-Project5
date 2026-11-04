# Workflow 2 bounded smoke pilot: offline preparation complete, live blocked

No real-model workflow runs were executed. All 12 planned rows are NOT_RUN_CONFIGURATION. Provider requests: 0; pilot spending: USD 0. The first clean logging sanity check was not dispatched. This is a configuration-gate stop, not a budget-exhaustion result, model failure, nonactivation, or recovery success.

## Source and preservation

Inspected the actual local codex/workflow2-cost-accounting worktree at commit 9c6532ff7630fa69e30e1a3780fb24136d787ed0, including its uncommitted recovery.py and new cost_metrics.py/provider_accounting.py. The source commit alone does not identify these changes: manifest.json records the complete file hash inventory and status; source_snapshot retains the accounting implementation, patch and documentation. The older recovery implementation was not substituted. All source files and worktree status remained unchanged. The main checkout's pre-existing .DS_Store and three modified bytecode files were preserved. No merge, commit or push occurred. New artifacts are isolated under this new output directory.

## Selected case and frozen plan

BASE-0004 combines incorrect_invoice and app_crash. Both scenario records exist, both technical/billing helpers are reachable, and all four variants retain the original request, scenario and four-iteration limit. Historical strict-rubric review gives the clean answer a provisional PASS; this is not human-finalized and is not a judgment on any new output. No case was swapped based on new live quality or activation.

The exact four IDs are BASE-0004-NONE, BASE-0004-QA_CORRUPTION, BASE-0004-HELPER_CORRUPTION and BASE-0004-TIMEOUT. Each uses unprotected, full_restart, then always_verify, in that order. All three clean controls precede QA, helper-corruption and timeout conditions. The manifest freezes all 12 entries and original/effective fault configurations. The QA variant uses the existing requested qa_first_missing_once_v1 profile; helper and timeout configuration remain unchanged. The helper target is billing. Every fixture uses a fresh state, injector and 40/40/40 dispatch budget. Full restart stays within its logical run.

Scripted QA evidence shows app_crash remains OPEN after incorrect_invoice is resolved, missing_issue is app_crash, the replacement label is incorrect_invoice, and iteration 1 leaves another Router iteration. Actual ledger history supports these facts; a separate boundary unit check also captures OPEN/RESOLVED state. Expected labels are used only by offline fixtures, never a live model or recovery policy. Offline eligibility and activation do not establish live eligibility or activation.

## Blocking configuration and provider accounting

The saved prior pilot configuration identifies api-glm-5.3-flash, temperature 0, timeout 120 seconds, SDK max_retries=0, serial execution without an explicit pacing delay. The configured host is tritonai-api.ucsd.edu. Credentials were not printed or copied.

The unchanged OpenAIClient.complete and saved manifests omit max_tokens/max_completion_tokens. No verified provider-default completion ceiling or exact-route configured USD rates were found. The official update page names api-glm-5.3-flash but supplies no pricing or ceiling; the public catalog content retrieved did not establish this exact route's rates. Different-model or different-provider prices were not substituted:
- https://docs.tritonai.ucsd.edu/llm-api/updates
- https://docs.tritonai.ucsd.edu/models

The requested pre-request conservative cost reservation cannot be implemented honestly using unknown prices and an unverified completion ceiling. Therefore no paid dispatch is permitted. The unchanged ceilings remain 150 provider requests and USD 0.50; no lower project spend limit was located in configuration. Account-specific remaining allowance was not established. No limits were raised.

The recovery CLI is offline only. The prior live pilot entry point lacks recovery-policy integration and pilot-wide cost reservations. provider_accounting.complete_observed is the correct response-usage seam for a future thin runner. The generic OpenAIClient uses SDK defaults, whereas the saved approved pilot explicitly selects zero retries: a future runner must restore the saved pilot's max_retries=0 and timeout=120, not silently inherit generic defaults. The v2 adapter intentionally leaves provider_attempt_count unknown; a future transport/request ledger must count observable requests, reconcile them with application calls, and reserve before dispatch. No new live runner with a misleading execution flag was added while mandatory pricing/configuration is unavailable.

To unblock: verify the exact gateway route's input/output rates and completion ceiling, or explicitly approve a fixed completion cap if it changes the saved configuration. Then implement and offline-test request reservations, observable request counting and the thin instrumented live runner. Keep all settings identical across the frozen policies. Run the first clean control as a usage/identity sanity check and stop on broken tracing before dispatching remaining rows. Omitted provider usage must remain unknown. These are outstanding prerequisites, not evidence the live harness has passed.

## Offline behavior and reconciliation

Twenty existing test_cost_metrics, test_cost_behavior and test_recovery tests passed (20.313 seconds). Twelve explicitly SCRIPTED_OFFLINE_ONLY matrix fixtures also completed. Their complete events, attempts, artifacts, calls, failed attempts and recovery reasons are saved in offline/. They are not paid workflow runs and do not populate the live summary metrics.

| Condition | Unprotected | Full restart | Always verify |
|---|---|---|---|
| Clean | No mutation | No mutation, no restart | No mutation |
| QA corruption | One mutation; Router revisits resolved issue; later completes | Same natural correction; zero full restarts | One mutation rejected before Router; one QA stage retry |
| Helper corruption | One altered record accepted; structural completion does not establish quality | Final record mismatch triggers one full restart | Altered record rejected before prose generation; one helper retry |
| Simulated timeout | One timeout status; helper unavailable then later natural continuation | Helper timeout triggers one full restart | Timeout rejected; one helper retry |

Timeout is immediate simulated status injection, not a measured network deadline or five-second wait. All nine fault fixtures mutated exactly once. These observations establish preflight applicability only. No claim about real-model recovery or robustness follows.

The reducer reproduces each fixture's metrics exactly; unique call IDs and terminal counts reconcile, and combined tool_calls equals business_tool_calls plus verification_calls. Failed/rejected/retried/restarted producers and discarded reasons remain in the original ledgers. Scripted model usage stays null with explicit unknown-usage counts, not invented zero tokens or USD charges. E2E, verification and interval-union repair latencies remain separate overlapping categories and are never added together. Provider attempt counting, real usage capture, real token costs and the first-clean sanity check are NOT VALIDATED LIVE.

## Quality review and decision

HUMAN_REVIEW.md has 12 planned review rows and supporting_records.json contains the exact scenario evidence. There are no retained live answers, discarded live intermediate answers or quoted live claims to assess. Every new quality judgment is NOT_ASSESSED; no scripted answer is presented as a real answer. The strict support-human-v1 rubric remains unchanged, including FAIL for unsupported refund timing/destinations or claims of confirmed technical repair. Future judgments must remain provisional pending human review and use no paid judge calls. Historical provisional quality does not qualify any new paired control for recovery claims.

Do not proceed to the 48-run live pilot yet. Offline eligibility and accounting checks passed, but mandatory spending configuration and the real-provider integration sanity check remain unresolved. This preparation supplies no statistical failure/recovery estimate and no general robustness claim.

Reproduce offline preparation with the exact command in REPRODUCE.txt. It creates a new directory and refuses overwrite. prepare.py is an offline-only preparation tool; there is no claim that this command executes a live pilot.
