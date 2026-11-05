# Saved-answer GPT evaluation: prepared, blocked before paid calls

**No GPT generation model is accessible with the configured TritonAI key. No paid inference calls have been made.** The authenticated `/v1/models` response lists eight models, none a GPT generator; `api-openai-privacy-filter` is a privacy classifier, not a GPT judge. There is no fallback to GLM and the key has not been sent to the direct OpenAI endpoint.

Open [SUMMARY.md](SUMMARY.md) for counts and budget, [preflight.json](preflight.json) for the precise access evidence, and [unfinished_items.csv](unfinished_items.csv) for every outstanding item. The configuration file is separate from the experiment's frozen configuration.

## Coverage and exact deduplication

- Primary experiment: 560 individual answers (480 retained, 80 discarded) and 240 final retained bundles.
- Infrastructure archive: six individual answers and five incomplete retained bundles, kept separate from experimental outcomes. An interrupted bundle is not represented as a completed user-facing answer.
- Total inventory: 811 items, mapped to 638 exact context hashes. Shared calls are permitted only for byte-identical canonical rubric-relevant input, including draft/bundle type, disposition, assigned/expected issues, reference and observed records, source support text, and workflow context.
- Identity mappings retain scope, slot/run/event IDs, individual answer hashes, bundle member hashes, scenario, policy, repetition, and source paths. Policy/scenario labels and existing verdicts are excluded from judge inputs. Duplicated final bundles can span scenarios when their actual assessment context is identical.
- Every primary `helper_accepted` event and every archive answer is accounted for. Each input includes the original authoritative records and explicitly separate observed records. Prior answers within the same attempt supply coordination context; the judge is not told that discarded drafts were delivered to customers.

## Pricing, access, and the USD 3 ceiling

The live public TritonAI catalog lists candidate `gpt-6-luna` at **$0.10 per million input tokens and $0.50 per million output tokens**. This is an economical candidate for the planned rubric pilot, not a model actually used or an account-access claim. Access must first be granted to that model through the configured endpoint, `https://tritonai-api.ucsd.edu/v1`.

Public rates are verified, but a strict cost ceiling additionally needs an endpoint-specific bound on all billable attempts and fees. Public metadata does not establish how gateway-hidden retries or additional charges are reflected in response usage. Accordingly, `billing_contract_verified` remains false and `max_billable_attempt_multiplier` remains null in judge_config.json. The placeholder zero request fee is **not** a verified contract. Do not merely flip this gate to bypass missing evidence. Obtain documented account/endpoint billing treatment, record its evidence, and set conservative bounds before executing paid calls. No support message has been sent automatically.

Planning estimate: approximately **$0.8975** for all 638 unique inputs, using input UTF-8 bytes divided by three and 1,500 generated tokens per request. This is a heuristic, not a quote or guarantee; see cost_estimate.json. The proposed output ceiling is 3,000 tokens per request, including reasoning tokens. If a response is truncated, it is an evaluation error, not an answer failure; evidence is never shortened silently to fit a price target.

The budget reservation does not rely on that heuristic. It uses the catalog's entire 922,000-token input capacity and the 3,000-token output limit: **$0.0937 per pending request before any verified billing multiplier or request fee**. The reservation is persisted and fsynced before dispatch, then reduced only when valid usage supports the release. A conservative usage-derived charge uses full input price (no cache discount) and aggregate completion tokens (including reasoning). Missing usage, transport errors, unknown usage categories, or crashes retain the reservation. The runner stops before a new reservation would exceed USD 3.00. Full completion within the budget is not guaranteed.

`budget_ledger.json` is the single persistent ledger for pilot, later execution, errors, and resumed sessions. Do not delete, reset, or create another ledger to evade the ceiling. An exclusive lock prevents concurrent runners. There is no SDK and no client retry; system curl is used with its user configuration disabled, TLS verification enabled, retries zero, and no redirect following. Credentials are passed over stdin, never in command-line arguments or saved artifacts. Explicit retries are currently disabled; an attempted item is never automatically billed again.

## Resume after resolving the blockers

Use the same directory, inventory, and ledger. The following commands are relative to the repository root; `/usr/bin/python3` is Python 3.9.6 on the current machine. On another machine, use Python 3.9+ and system curl with a valid trust store, and resolve the same repository/source files before transferring the ledger. The saved source paths identify this audit machine.

1. Obtain GPT access at TritonAI (or explicitly configure and verify a different endpoint with its own authorized key and pricing). Do not assume a TritonAI key works directly with OpenAI. Keep secrets in a local environment or ignored file. `JUDGE_API_KEY` / `JUDGE_BASE_URL` can override the original configuration without editing it.
2. Before any paid call, document all applicable rates, token-bound enforcement, billable attempt multiplicity, and fees in the separate judge_config.json. Never change model/prompt/pricing after paid requests without retaining the existing ledger and explicitly accounting for previous versions. The current runner stops on configuration drift.
3. Recheck access and catalog prices:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1/judge_workflow2.py preflight --env-file /Users/yanghede/Downloads/CSE291A-Project5/.env
```

4. When preflight reports no blockers, run the ten-job diverse pilot (it is part of the same USD 3 ledger):

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1/judge_workflow2.py pilot --env-file /Users/yanghede/Downloads/CSE291A-Project5/.env
```

5. Inspect every pilot judgment and its full input for scope mistakes, corrupted-record grounding, omitted issues, premature closure, bad excerpts, and schema errors. The plan covers clean/all fault scenarios, drafts/bundles, and discarded intermediates; exact duplicate contexts share calls. Only after that inspection, record the actual inspector and findings:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1/judge_workflow2.py approve-pilot --inspector "ACTUAL_INSPECTOR" --notes "ACTUAL_PILOT_INSPECTION_FINDINGS"
```

This approves the evaluation procedure only; it does not populate human answer-quality fields. If the pilot reveals prompt errors, do not approve it or reinterpret its labels under a new prompt. Preserve the costs and revise explicitly before proceeding.

6. Continue under the same price/configuration and reuse valid pilot judgments:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1/judge_workflow2.py run --env-file /Users/yanghede/Downloads/CSE291A-Project5/.env
```

After a process interruption, first run the local-only reconciliation command. It recovers already persisted responses without another API call; a reservation with no saved response remains unresolved and blocks further dispatch pending investigation:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1/judge_workflow2.py reconcile
```

Do not rerun `prepare`: it refuses to overwrite an existing inventory. A resumed `run` skips valid judgments, preserves explicitly errored items in unfinished_items.csv, and does not automatically retry them. Resolve errors separately without dropping their costs or treating them as answer FAIL.

## Output meanings

- `judgments.jsonl`: valid judgments mapped back to original item identities. Currently empty because no judge calls ran.
- `review_sheet.csv`: all 811 items, criterion label/reason/evidence columns and separate human fields. Pending items are NOT_EVALUATED and human fields are UNREVIEWED.
- `human_followup_queue.csv`: assessed non-PASS items, evaluation errors, and a reproducible 10% rounded-up random sample of eligible PASS items (seed 20261104). Currently header-only; that does not approve pending items.
- `unfinished_items.csv`: every exact unfinished item, including source paths and hashes.
- `scenario_policy_breakdown.csv`: separate primary/archive and draft/bundle denominators.
- `run_quality.csv`: local aggregation of retained-draft judgments plus independent bundle assessment. Uses DATA_ISSUE separately for record-alignment failures and never infers PASS from missing judgments.
- `system_prompt.txt`, `jobs.jsonl`, `inventory.jsonl`, `prepared.json`: frozen prompt/context, exact duplicate mapping and provenance hashes. `response.schema.json` documents the response structure; the code additionally checks actual quotes and source-field values.
- `responses/`, `judgments/`, `errors/`: per-request checkpoints created only as work proceeds. Their initially empty state is expected.
- `budget_ledger.json`, `judge_config.json`, `preflight.json`, `cost_estimate.json`: persistent cost controls and current blockers.
- `offline_tests.txt`: 25 offline tests covering schema/evidence validation, aggregation, budget boundaries, unknown usage, locking, resume, stale prompts and no-GPT access gating.

Source content is untrusted data, never judge instructions. Automated validation proves exact quotation and field identity, not that the judge's reasoning is correct. All eventual labels are LLM-assessed, not human-verified. The original frozen rubric, prior human judgments, experimental model settings, and raw results remain unchanged. Deterministic execution metrics remain in the prior English audit package; the judge never estimates latency or fault activation.

## Sources checked

- [TritonAI model access and pricing](https://docs.tritonai.ucsd.edu/llm-api/models): authenticated model access is distinct from the public catalog.
- [TritonAI public catalog](https://tritonai-api.ucsd.edu/public/model_hub): saved response in public_model_catalog.json, with selected-model details also in preflight.json.
- [TritonAI API reference](https://docs.tritonai.ucsd.edu/llm-api/api-reference): configured base URL, models and inference routes.
- [TritonAI billing FAQ](https://tritonai.ucsd.edu/developer-apis/faq.html): cloud billing and account approval treatment.
- [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): upstream max_completion_tokens includes visible and reasoning tokens; gateway-specific enforcement still requires verification.
