# Workflow 2: saved-answer LLM assessment

Start with **SUMMARY.md** for current coverage/cost and **RESULTS.md** for the final interpretation when available. This package uses `api-glm-5.3-flash` through TritonAI, explicitly authorized after the selected GPT model proved inaccessible. The original experiment also used GLM Flash: shared-model judging bias limits independence. These assessments are **LLM-assessed, not human-verified**.

## Scope

811 review items map to 638 byte-identical canonical-context jobs: 560 primary drafts (480 retained, 80 discarded), 240 primary final retained bundles, six archived infrastructure-attempt drafts, and five incomplete archived bundles. Archived attempts never increase the 240 experimental slots. Exact-context deduplication preserves all item/run/event/slot identities and answer hashes in inventory.jsonl. Draft inputs include the question, expected issues, original and observed records, support material, disposition and earlier same-attempt answers. Bundle inputs include all retained answers. Policy/scenario names and previous verdicts are withheld from judge inputs.

The frozen baseline rubric supplies five criteria: record_alignment, relevance, grounding, coverage and status_responsibility. Evidence validation checks exact answer quotations, JSON pointers and source values, plus deterministic overall aggregation. It cannot establish that an LLM's interpretation is correct. Individual draft quality excludes record alignment from the answer-only aggregate; whole-run quality includes record alignment and independently assessed bundle coverage. See system_prompt.txt, response.schema.json and judge_workflow2.py for the exact rules.

## Human review

Open **human_followup_queue.csv** first, then **review_sheet.csv** for the complete inventory. Read the user question and original authoritative records together with observed records and the answer. Verify each quoted passage/source field and judge explanation against the trace. Fill each separate `human_*` criterion, human verdict, reviewer, timestamp and rationale. All human fields start UNREVIEWED; machine assessments do not authorize human PASS.

The queue contains non-PASS or uncertain judgments, flagged answers, evaluation errors, and a seeded 10% rounded-up sample of other PASS answers. Queue membership only controls review order. Other answers remain unreviewed. Discarded drafts diagnose fault propagation and interception; they are not delivered final answers. Retained drafts and final bundles determine the LLM-assessed delivered quality. Archive drafts diagnose interrupted infrastructure attempts separately.

## Budget and provenance

One persistent **budget_ledger.json** covers every pilot, failed response, retry and resumed call. Published TritonAI rates are $0.15/M input and $0.50/M output. All prompt tokens are charged at the full input rate, even cached tokens; aggregate output includes reasoning. This is conservative tariff accounting, not a provider invoice. Unknown usage keeps its entire reservation. Automatic HTTP/SDK retries are disabled; up to two explicit retries are recorded per configuration/job.

The task ceiling is $3; $1 remains an unspent precautionary holdback. Each request reserves the entire published 500,000-token input capacity plus its output cap before dispatch. No further request is admitted if that would exceed the dispatchable balance. Unobservable provider charges cannot be guaranteed from public pricing alone; billing_contract_verified remains false. No claim of an unconditional all-in invoice guarantee is made.

The initial 4,000-output-token pilot exhausted its limit twice on a difficult corrupted answer. Its code/configuration, judgments and errors are retained under history_output_cap4000. The revised pilot uses 12,000 output tokens including reasoning. Earlier costs remain charged, and those judgments are not reused under the revised configuration. config_history.json binds historical requests to their exact configuration. The prompt and original experimental evidence were not altered.

## Reproduction

Run from the repository root. Credentials are read from the existing local .env; keys are never saved in this package. The separate judge_config.json selects the judge, so the experiment's OPENAI_MODEL does not need to change.

```dotenv
OPENAI_API_KEY=YOUR_TRITONAI_KEY
OPENAI_BASE_URL=https://tritonai-api.ucsd.edu/v1
OPENAI_MODEL=api-glm-5.3-flash
```

```sh
P=results/workflow2_phase1_20261103_210112/analysis_llm_judge_20261104_v1
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 "$P/judge_workflow2.py" report
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s "$P" -p test_judge.py
```

`report` and tests are offline. `pilot` and `run --env-file /absolute/path/to/.env` make paid calls. Do not reset the ledger or run prepare again. `run` resumes valid judgments; repeated invocation can make the configured bounded retries for evaluation errors. A pending reservation blocks further calls until its saved response and usage are reconciled. Do not blindly clear it.

## Files

- SUMMARY.md / summary.json: live coverage, cost, unresolved counts.
- review_sheet.csv: complete inventory, labels, explanations, evidence, identities and human fields.
- judgments.jsonl: valid assessments mapped to original items.
- unfinished_items.csv: precise items without a valid assessment, never silently excluded.
- scenario_policy_breakdown.csv and run_quality.csv: grouped outcomes and combined retained/bundle quality.
- human_followup_queue.csv: human follow-up and random PASS audit sample.
- jobs.jsonl / inventory.jsonl / source_hashes.json / prepared.json: context, mappings and frozen hashes.
- requests / responses / judgments / errors: checkpoints and exact request payloads; historical errors may coexist with a later valid judgment.
- budget_ledger.json / judge_config.json / config_history.json: cumulative accounting and configuration provenance.
- history_before_available_model: earlier blocked GPT preparation, retained as history.

Original traces and prior review evidence are read-only. The prior English offline audit retains deterministic execution/activation/latency/token metrics and the Phase 1 requirements matrix. One repetition per case does not demonstrate repeatability or stable latency improvement.

Sources: [TritonAI catalog](https://tritonai-api.ucsd.edu/public/model_hub), [TritonAI access documentation](https://docs.tritonai.ucsd.edu/llm-api/models), [GLM thinking behavior](https://docs.z.ai/guides/capabilities/thinking-mode).

Where only an overall label disagrees with the repository rule, derive_aggregates.py derives it locally from the unchanged criteria and revalidates every evidence field. The original model label is retained in local_aggregation_audit.json and the raw response. This does not repair or accept incorrect quotations or source values.
