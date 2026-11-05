# Local recovery smoke pilot

Run from the repository root with the existing virtual environment and .env provider connection:

```bash
.venv/bin/python run_recovery_smoke_pilot.py --execute --output "results/workflow2_recovery_smoke_local_$(date +%Y%m%d_%H%M%S)"
```

Omit --execute for offline preparation. Outputs must be new directories.

Pricing is optional metadata. No pricing file, a missing file, verified=false, or null price/limit fields permits execution with unknown costs recorded as JSON null. No prices or verification claims are invented. With unavailable pricing, no completion parameter is added, preserving the saved pilot's provider-default generation settings; the USD gate is inactive. The 150-request ceiling remains enforced. A complete verified configuration supplied through --pricing-config retains the conservative USD 3 reservation gate and explicitly configured completion cap. Invalid non-null configuration values still produce a configuration error.

The original run_live_pilot.py and workflow/recovery modules are unchanged by this optional-pricing update. Saved model, temperature, 120-second timeout, zero SDK retries, four-iteration limit, per-run 40/40/40 dispatch budgets, fault configurations, policies and stopping conditions are preserved. Clean controls run first, followed by QA corruption, helper corruption and timeout; each condition uses unprotected, full_restart and always_verify. BASE-0004 is frozen for all 12 logical runs. Restart attempts remain within the original run.

The first clean control checks complete streamed traces, provider identity and usage linkage, and metric reconciliation before subsequent runs. Missing provider usage stays unknown. API errors are recorded by exception type and HTTP status without credential-bearing error text; the remaining runs stop under the existing provider-error policy. No automatic selective reruns occur.

Each run saves trace.jsonl, provider_requests.jsonl, provider_usage.json, metrics.json, result.json, answers.json and logging_sanity.json. Top-level manifest.json, summary.csv, pilot_status.json and human_review.json retain settings, all 12 planned outcomes, request accounting and answers with scenario evidence. Actual tokens, calls, retries, latency and fault/recovery outcomes remain recorded independently of price availability. Quality remains UNREVIEWED, separate from structural completion. Unknown costs are null, never zero. Source import provenance remains in recovery_smoke_source.json.

Validation:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest test_recovery_smoke_pilot -q
```

Eight tests pass with sockets blocked, including all 12 combinations and no/missing/unverified/null pricing configurations, usage omission, provider failures, budget stops and first-control sanity stops. Mock rates are fixtures, not real pricing.
