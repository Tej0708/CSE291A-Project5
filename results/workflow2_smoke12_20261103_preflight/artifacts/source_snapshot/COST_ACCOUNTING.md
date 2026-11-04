# Workflow 2 cost accounting, support-cost-v2

Base: `9c6532ff7630fa69e30e1a3780fb24136d787ed0`, fetched from
`yanghede88/CSE291A-Project5`, branch `workflow2/recovery-baselines-v1`.
Working branch: `codex/workflow2-cost-accounting`.
The recovery policy remains `support-recovery-v1`; only measurement is versioned
as `metrics_schema_version: support-cost-v2`.

This document supersedes the cost-accounting limitations in RECOVERY_BASELINES.md
for **new recovery runs only**. That document, RECOVERY_VALIDATION.md, frozen
source files, datasets and historical results are preserved verbatim. No historical
run is relabeled as v2. Structural completion remains separate from answer quality:
`task_quality=UNREVIEWED`, `recovery_success=null`.

## Inspected Workflow 1 references and unresolved differences

All references were read at `83cda0815655078936424000f2aa5d4332ef1f3b` on
`Tej0708/CSE291A-Project5`, branch `hiba-dev`. The GitHub connector returned 404;
Git fetch succeeded, so no requested reference is missing.

- [README](https://github.com/Tej0708/CSE291A-Project5/blob/83cda0815655078936424000f2aa5d4332ef1f3b/README.md)
- [phase1-metrics.md](https://github.com/Tej0708/CSE291A-Project5/blob/83cda0815655078936424000f2aa5d4332ef1f3b/docs/phase1-metrics.md)
- [metrics.py](https://github.com/Tej0708/CSE291A-Project5/blob/83cda0815655078936424000f2aa5d4332ef1f3b/experiments/metrics.py)

The recovery workflow and run_clean aggregation were also inspected to verify
cross-attempt timing behavior.

| Workflow 1 field or definition | Workflow 2 v2 field | Alignment and remaining difference |
| --- | --- | --- |
| model_calls | metrics.model_calls | Completed + failed application calls; incomplete starts separate. Neither establishes exact underlying SDK request count. |
| tool_calls | metrics.tool_calls | Business + verification terminal calls. W1 only includes verification_completed in this total; W2 also includes verification execution failures. |
| No separate public business count | metrics.business_tool_calls | Includes support-document retrieval, business-record reads and fresh verification reference reads, successful or failed. |
| verification_calls | metrics.verification_calls | W1 pairs verification_failed to remove pending starts but omits those records from count and latency. W2 counts both failure and rejection; this deliberately fixes the gap. |
| tool_latency_ms | metrics.business_tool_latency_ms | Same service-time category. Nested reference reads are also inside verification time. |
| verification_latency_ms | metrics.verification_latency_ms | W2 includes verifier execution failures. A rejected verdict is a completed verification, not an execution failure. |
| e2e_latency_ms | metrics.e2e_latency_ms | W2 uses one perf_counter origin through the logical run endpoint. W1 sums per-attempt trace endpoints in run_clean, omitting time between attempts. |
| repair_latency_ms | metrics.repair_latency_ms | W1 _timing recognizes stage_retry/tool_retry and corresponding repaired events only. Its full-restart wrapper has no full-restart interval. W2 explicitly times both types. Exact equivalence is not claimed. |
| input/output/total_tokens; reported_* | metrics.provider_usage: input/output/total_tokens; known_* | W2 keeps provider-reported fields nullable, exposes separate derived subtotal, and makes full totals unknown when any call is incomplete. W1's terminal-only totals do not incorporate unresolved starts. |
| Discarded-work definition | metrics.discarded_calls, discarded_by_kind | Failed calls, rejected-output producers and actually superseded candidate/attempt producers; unique call IDs. Successful detection/reference checks are retained. |
| Combined tool budget including verification | budget_config and budget_semantics | W2 retains separate tool and verification dispatch budgets. The combined reporting metric does not replace either budget. |
| Task/checker success | task_quality and recovery_success | W2 structural completion is not a prose-quality PASS or proven recovery success. Verifier coverage also differs. |

Proposed shared timing definition: one monotonic logical-run origin, explicit
recovery IDs and execution-start boundaries, stage acceptance / restarted-attempt
end boundaries, failed/unfinished intervals through the recorded endpoint, and
interval-union repair time. Both projects should adopt this definition before
pooling repair or end-to-end latency results. Keep budget policies and verification
coverage as explicit experimental dimensions.

## Log and metric contract

The result contains `calls`, `artifacts`, `recoveries`, `events`, `attempts`,
`budget_config`, `budget`, `source_revision`, `model_config` and `metrics`.
`source_revision` includes HEAD and hashes of the actual accounting, recovery,
frozen LLM and provider adapter files, so an uncommitted worktree is not silently
represented as identical to HEAD. The existing CLI additionally records dataset
SHA-256 and its exact arguments. Run records retain fault configuration, mode,
max_iterations and actual starting budget configuration.

Each dispatched call has a globally unique `call_id`, kind, stage, attempt,
nullable duration/usage, output_artifact_id and discarded_reason list. The output
ID is reserved at dispatch: a failed/incomplete call does not prove that an output
exists. Completed events contain the output. `artifact_id` identifies the stage
candidate to which a model/business producer contributes; that candidate records
its explicit source_call_ids. Reference reads and verification results have their
own call output IDs and are not producers of the checked candidate.
`parent_call_id` links nested reference reads to their verifier.
`previous_event_id` is ordering only and is never used to infer causal links.

For each model, business_tool and verification category:

- `started_*_calls = *_calls + incomplete_*_calls`.
- `*_calls` counts completed and failed terminals, excluding blocked dispatches.
- `failed_*_calls` counts execution exceptions; `rejected_verification_calls`
  counts completed negative verdicts. `verification_decision` links verdicts to
  both verification_call_id and the candidate artifact.
- `*_latency_ms` is the sum of all dispatched durations, or null when any duration
  is unknown or any call is incomplete. `known_*_latency_ms` is a known subtotal.
  Empty categories legitimately have zero calls and zero service time.

`summarize()` accepts a reconciled call ledger and rejects duplicate IDs rather
than double-counting them. The runner owns each ledger record and updates it once
at termination. Incomplete calls (including interrupted calls) remain incomplete.
It does not guess terminal events from neighboring events.

The original `budget.model_calls`, `budget.tool_calls`,
`budget.verification_calls` and `attempts[].calls` remain **dispatch budget counters**,
not the new terminal-call metrics. `max_tool_calls` still excludes verification;
reference reads consume tool budget even inside a verifier. A verifier that starts
but fails because its nested read is blocked counts as a failed verification;
the blocked reference read itself is excluded. Default limits remain 40/40/40.

All new latency fields use milliseconds from monotonic perf_counter. Existing
elapsed_seconds fields are retained for compatibility; attempts also expose
duration_ms, including failed attempts. End-to-end timing includes attempts,
verification, provider pacing/retries/waits and state reset, through run_finished.
Summary serialization occurs after that endpoint. Never add model, business-tool,
verification, repair and e2e durations: they overlap.

Recoveries record recovery_id, type, trigger reason, originating attempt/stage,
start/end event IDs, interval and outcome. Full restart begins before supersession,
fault disabling and fresh state construction; it ends at restarted attempt
completion. Stage retry begins before replacement work and ends at acceptance.
Failed intervals extend to run_finished, with endpoint_event_id and failed outcome.
An externally interrupted run can have an unresolved interval; the summarizer
uses its supplied recorded endpoint, never inventing a finish. Union merges
nested and overlapping intervals. Detection before recovery_start is excluded.
`accepted` and `completed` describe structural outcomes only.

Natural correction is not included in repair time or policy recovery counts.
The natural_correction event denotes an actually accepted replacement of an
existing issue candidate, with outcome=output_replaced and UNREVIEWED quality;
it is not proof of semantic repair. Merely routing again does not discard work.
Only the explicit assignment replacing the current accepted candidate does so.

## Provider usage and SDK audit

`provider_accounting.complete_observed` wraps the actual SDK response boundary
through a shallow client/proxy, then invokes the original, unchanged
OpenAIClient.complete implementation. It delegates to the original SDK transport
with identical arguments. It changes no prompts, model settings, retry settings,
credentials or budgets. It never logs headers, credentials or SDK representations.
Custom complete implementations retain their behavior and unknown usage.

The frozen OpenAIClient constructor does not set max_retries. The installed SDK
source used for this audit sets DEFAULT_MAX_RETRIES=2. Each new run records the
actual client._client.max_retries when inspectable; unknown remains null.
Internal SDK attempts are not exposed by this boundary: one application call may
contain multiple provider requests. `provider_attempt_count=null` is intentional.
Do not follow the older baseline document's advice to disable SDK retries as part
of this accounting change; doing so would change the experimental configuration.

Input, output and total tokens are captured independently from the response.
A missing total is not filled from input + output. `known_*` values are reported
subtotals; full totals are null with missing fields or incomplete calls.
`derived_total_tokens_known_subtotal` is separately labeled and accompanied by
its contributing call count. `unknown_usage_calls` includes model calls with any
missing field, including failed/incomplete calls; incomplete_calls is also exposed.
A usage-bearing response followed by local parsing failure retains its usage.
No usage from an unobservable internal SDK attempt is inferred. Reported usage is
not a billing guarantee. Scripted application calls are fixtures, not paid calls.
The legacy top-level provider_tokens stays null; consume metrics.provider_usage.

## Discarded work

Each call has a deduplicated list of reasons: execution_failed,
verification_rejected, stage_retry_superseded, full_restart_superseded or
output_replaced. Counts include model, business_tool and verification categories,
with an explicit breakdown. Failure counts even without a later retry.
A rejected helper record marks its business-record producer (and any already
produced model output of that composite candidate); a rejected QA candidate marks
its model producer. The document read is not rejected merely because the record
is rejected; it is discarded only if the candidate is actually superseded.
Deterministic candidates can have zero model producers.

A retry supersedes the rejected candidate's producer calls; a restart supersedes
the prior attempt's stage producers. Successful verifiers and their successful
reference reads remain useful diagnostic work. Failed verifiers/reference reads
are discarded execution failures. Corruption exposure alone does not discard any
call. Diagnostic log retention does not control supersession.

All discarded resource costs remain in overall counts, latencies and token
subtotals. Discarded tokens use only the usage on those exact call IDs. Missing
usage and incomplete calls remain explicit in discarded_provider_usage.

## Historical recomputation eligibility

No historical summaries were overwritten or generated by this change.

| Historical evidence | Recomputable | Unavailable / incomplete |
| --- | --- | --- |
| Old recovery call_started event IDs + terminal call_id | Dispatched, completed/failed and incomplete counts by kind; combined tool terminal count; recorded call durations | Provider usage was null; unknown usage cannot become zero |
| Old elapsed_seconds and attempt elapsed_seconds | Recorded endpoint and attempt durations converted to ms, explicitly labeled legacy endpoint semantics | Exact new run_finished endpoint if no such event exists |
| Old stage_retry/restart_triggered events without execution-start/end IDs | Existing retry/restart counts | Exact repair intervals, reset/wait boundaries and interval unions |
| Old calls without candidate producer IDs | Explicit call failures and their known costs | Rejection/supersession discarded totals and associated token costs; adjacency is insufficient |
| Original formal and pilot traces with their own schemas | Only fields directly supported by their IDs, usage and durations after a schema-specific evidence audit | Missing recovery intervals and artifact relations; no blanket v2 conversion |
| Historical 0/40 activation results | Original activation observations and configuration | No recovery rate or new budget policy can be inferred |

Any future recomputation must use a separate output, preserve source revision,
original experiment configuration and original metrics version, and explicitly
mark unavailable fields. The new reducer deliberately has no legacy adjacency
fallback.

## Offline validation

Run from the worktree root with Python 3.10+ (validated here with Python 3.14):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s human_review_tool -p 'test_*.py' -v
```

The differential tests require the recorded base commit in local Git; they do
not fetch or run models. Network connections are blocked in the new fixtures.
The review UI's existing HTTP test requires local loopback access.
See accounting_validation/REPORT.md and its English example_log.json. No paid
experiment or real model API request was run. Timing overhead is expected;
behavior equivalence is not a claim of equal measured latency.
