# Workflow 2 partial-experiment handoff

## Verified state and cause

Continue `results/workflow2_phase1_20261103_210112` on branch `main`.
The frozen schedule is `phase1_v1/full_manifest.json`; its bytes match the manifest saved inside the results directory. There are **240 slots: 37 completed, 1 infrastructure error, 202 unstarted**. The errored slot is `BASE-0011__NONE__full_restart__r1`. Its receipt says `execution="error"`, not successful completion.

Provider dispatch 184 failed with `RateLimitError`, HTTP 429. Both `provider_requests.jsonl` and `provider_usage.json` omit the provider error code, message and Retry-After. **The evidence cannot distinguish temporary rate limiting from exhausted quota.** No quota-exhaustion claim is justified. The interrupted attempt's first two calls account for 706 known tokens; its failed call's usage and total cost remain unknown. All original result files, traces, metrics, journals and receipts are included unchanged.

## Environment and credentials

Use your own authorized credentials for the same TritonAI endpoint/model. Never copy another person's API key or commit `.env`. The implementation reads `OPENAI_API_KEY` and `OPENAI_BASE_URL`; `OPENAI_MODEL` exists as a client fallback, but this experiment explicitly loads its model from the frozen manifest, overriding that fallback. Existing shell environment values take precedence over `.env`.

From a clean clone:

```bash
git clone --branch main https://github.com/yanghede88/CSE291A-Project5.git
cd CSE291A-Project5
python3 -m venv .venv
.venv/bin/python -m pip install 'openai==2.48.0' 'httpx==0.28.1'
```

The saved environment uses Python 3.9.2, OpenAI SDK 2.48.0 and httpx 0.28.1. The execution and analysis runners otherwise use the standard library. Use Python 3.9 or newer supported by those dependencies. Git must be available for provenance recording. Install/setup commands do not launch the experiment.

Set `OPENAI_API_KEY` through your own secret manager or an ignored local `.env` containing your own key. Set the non-secret endpoint:

```bash
export OPENAI_BASE_URL='https://tritonai-api.ucsd.edu/v1'
```

Do not change the provider endpoint, model or generation settings to evade a provider limit. Confirm your account is authorized to use `api-glm-5.3-flash` on this endpoint. This handoff does not establish whether the original account's limit was temporary or quota-related.

## Verify offline before continuing

```bash
.venv/bin/python verify_workflow2_handoff.py \
  --run-dir results/workflow2_phase1_20261103_210112
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  test_phase1 test_phase1_full test_recovery_smoke_pilot test_infrastructure_continuation -q
```

The saved-result continuation test expects the original 37/1/202 handoff and uses a disposable copy with sockets blocked. Run it before live continuation; after the experiment progresses, use the verifier below instead of rerunning that fixed-snapshot regression. Do not edit source files after validation: the continuation plan binds their exact hashes.

## Exact continuation command — makes live calls when you run it

```bash
.venv/bin/python workflow2_phase1.py execute \
  --manifest results/workflow2_phase1_20261103_210112/manifest.json \
  --output results/workflow2_phase1_20261103_210112 \
  --resume \
  --continuation-plan results/workflow2_phase1_20261103_210112/continuation_plan.json
```

This skips the 37 completed slots, archives the interrupted directory byte-for-byte under `_infrastructure_attempts/BASE-0011__NONE__full_restart__r1/attempt_001`, retries its scheduled slot with a new run ID, and executes the remaining 202 slots in frozen order. Archiving occurs atomically under an exclusive lock when execution starts; the original evidence has not yet been moved. The manifest is never rewritten.

The retry is an explicitly authorized **infrastructure re-execution**, not an experimental `full_restart` recovery or an additional study repetition. Its identity links the original archive and continuation plan. Original usage remains separately available and included in cumulative request numbering; the next provider dispatch is 185. The plan permits only this one infrastructure retry. A subsequent provider error stops execution and needs a new decision; it is not silently skipped or automatically retried. A partial slot without a receipt also blocks replay. Do not delete evidence or an active `.execution.lock`; inspect process ownership before removing a genuinely stale lock.

Settings stay `api-glm-5.3-flash`, temperature 0, other generation parameters omitted/provider defaults, timeout 120 seconds, SDK retries 0. The experiment remains 20 cases × four scenarios × three policies × one execution. Seed-42 case order, per-case clean-first controls, policy rotation, single-shot fault semantics across policy retries/restarts, per-run limits and the complete 240-slot schedule are unchanged. TIMEOUT is synthetic status injection. The full experiment has no application-wide request ceiling; provider limits still apply.

The original resume code skipped `execution="error"` receipts. The included minimal fix makes ordinary resume refuse infrastructure errors and requires the explicit continuation plan. The plan records the runner/logging code amendment and checks all other frozen code/data hashes. Future provider errors log sanitized code/type/message and Retry-After when available; credentials and request headers are excluded.

## Verify completion and interpret outcomes

```bash
.venv/bin/python verify_workflow2_handoff.py \
  --run-dir results/workflow2_phase1_20261103_210112 --require-complete
```

This checks the 240 unique scheduled tuples, unchanged manifest/source plan, original/completed evidence hashes, receipt/result identities and hashes, and provider-accounting sanity. Exit status zero with `valid_execution_outcomes: 240` means every primary slot has a recorded terminal experimental outcome (`completed` or `failed`). Error, budget exhaustion, partial and unstarted slots do not satisfy completion. Experimental task failures must remain failures, not be selectively rerun.

**Completed execution is not an answer-quality PASS.** Model/machine judgments are not human approval. This single-repetition descriptive study does not establish stable latency speedups. The original 11 PASS / 1 FAIL smoke judgments remain provisional and unchanged.

## Post-run analysis and human review

```bash
.venv/bin/python workflow2_phase1.py analyze \
  --run-dir results/workflow2_phase1_20261103_210112 \
  --output results/workflow2_phase1_20261103_210112/analysis_after_continuation_v1
cp -n results/workflow2_phase1_20261103_210112/analysis_after_continuation_v1/review_template.csv \
  results/workflow2_phase1_20261103_210112/human_reviews.csv
```

Review the actual retained and discarded answers with their original/observed records and traces. Fill the five criteria (`record_alignment`, `relevance`, `grounding`, `coverage`, `status_responsibility`) with PASS, FAIL, UNCERTAIN or UNREVIEWED and supply `reviewer`, `review_timestamp` and `rationale`. Do not alter event IDs or answer hashes. Blank human-review fields remain unreviewed. `human_verdict` is an optional annotation; criteria drive aggregation.

After completing review:

```bash
.venv/bin/python workflow2_phase1.py analyze \
  --run-dir results/workflow2_phase1_20261103_210112 \
  --reviews results/workflow2_phase1_20261103_210112/human_reviews.csv \
  --output results/workflow2_phase1_20261103_210112/analysis_human_v1
```

Use a new analysis output directory for every revision. `measurements.json` contains the 240 primary slots; `infrastructure_attempts.json` separately preserves the archived interruption's metrics and provider usage. Add archived usage separately when reporting total operational expenditure, without attributing it to experimental policy recovery overhead. Unknown failed-call usage is not zero. The original smoke and historical baseline evidence are retained in the repository.
