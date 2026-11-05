# Infrastructure continuation after HTTP 429

Saved directory: `results/workflow2_phase1_20261103_210112`.
Verified receipts: 37 completed, one `execution="error"`, 202 unstarted.
The interrupted slot is `BASE-0011__NONE__full_restart__r1`.
Its third provider dispatch (global request 184) failed with RateLimitError / HTTP 429. The first two dispatches consumed 706 known tokens; failed-dispatch usage and cost are unknown. Neither journal nor usage export contains provider code/message/Retry-After. Temporary rate limiting versus exhausted quota cannot be determined from these artifacts. There is no confirmed quota-exhaustion basis for a teammate handoff.

Old resume treated an error receipt as a terminal slot and skipped it. New ordinary resume blocks on infrastructure errors. The explicit continuation plan authorizes one infrastructure re-execution, separate from the experimental full_restart policy. No SDK retries or experimental settings change.

The frozen manifest remains byte-identical. The continuation plan binds that manifest, all completed evidence, the original interrupted evidence, and the exact updated source hashes. Only the runner and provider logging source changes are allowed relative to the frozen manifest; model, prompts, recovery policy implementation, data and settings must match. This records the code amendment explicitly instead of regenerating the manifest or disabling all drift checks.

When execution starts, under the exclusive execution lock, the interrupted slot is atomically renamed to `_infrastructure_attempts/BASE-0011__NONE__full_restart__r1/attempt_001`. The same scheduled slot then starts fresh, followed by the 202 remaining slots, in the original order. All 37 completed slots are skipped and hash-checked. The original attempt remains an error; it is never relabeled successful. The new run has its own run ID and an infrastructure-retry reference in identity.json. The original three request dispatches remain counted for cumulative accounting, with the next request numbered 185.

No results are moved by offline preparation. A repeated use of the plan does not rearchive or authorize a second infrastructure retry. If the re-execution or another slot errors, dispatch stops and a new protocol decision is required. Partial runs still block automatic replay. No automatic sleep, rate-limit bypass, or quota assumption is introduced.

```bash
.venv/bin/python workflow2_phase1.py execute \
  --manifest results/workflow2_phase1_20261103_210112/manifest.json \
  --output results/workflow2_phase1_20261103_210112 \
  --resume \
  --continuation-plan results/workflow2_phase1_20261103_210112/continuation_plan.json
```

Post-run analysis uses the existing command and now also emits `infrastructure_attempts.json`. That file retains the archived attempt's full metrics and provider usage separately from the 240 primary measurements. Include that usage when reporting total operational expenditure; do not count it as an extra experimental repetition or as policy recovery overhead. Unknown failed-request usage is not zero.

```bash
.venv/bin/python workflow2_phase1.py analyze \
  --run-dir results/workflow2_phase1_20261103_210112 \
  --output results/workflow2_phase1_20261103_210112/analysis_after_continuation_v1
```

Future errors record allowlisted provider code/type/message and Retry-After when supplied, with configured credential redaction. Request headers, arbitrary exception bodies, and request objects are never serialized. Existing evidence cannot be retroactively enriched.
