# Helper scope prompt v3 — 2026-11-02

The inspected v2 prompt says to address only the assigned issue but does not
explain shared request ownership. This matches the task description. That omission
is a plausible contributor to the historical separate-ticket errors, not proven
causality. Scenario-provided refund amounts are valid synthetic facts.

The prompt in `csa_workflow/llm.py` now distinguishes helper answer scope from
customer request scope. It permits omitting other issues, prohibits resubmission
of already included issues and unsupported whole-case closure, and prohibits
invented claims about another helper's progress. It retains record grounding,
untrusted-input handling, uncertainty and technical verification requirements,
and explicitly permits conditional follow-up. No runtime context was necessary;
the existing five payload fields and function signature are unchanged.

Helpers store generated text as per-issue internal evidence. The audit runner
exports that text to traces, case results and answer_review.csv. The orchestrator
returns status/history; there is no final response agent or user-facing bundling
stage. No output rewriting or retries were added. Routing, QA semantics, fault
hooks, model/provider settings and iteration budgets are unchanged.

## Offline validation

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_clean_audit test_helper_scope
```

Result: 11 tests passed (5 existing audit tests and 6 new tests with subcases).
New checks capture the actual prompt/payload and preserve deliberately bad output;
exercise BASE-0003/0004/0007 in both billing-first and technical-first order;
exercise equivalent single-issue cases and all 40 clean cases; check tools across
all 200 variants and mutable-record isolation; and check valid/invalid QA labels
with raw-response preservation and fallback. Classifications and helper answers
are scripted in memory. Gold labels configure the test double only and are not
added to agent inputs. No provider client, credentials or network is used.
These tests establish integration and prompt construction, not live compliance.

## New live clean runs (not executed by this patch)

Use the existing configured model/provider. These commands may incur API costs.
The audit CLI always filters fault_type == "none" before applying --case; it has
no --fault option. Explicit --path avoids the older default dataset. Each command
creates a fresh timestamp/UUID subdirectory with exclusive creation, under a new
v3 output root. The manifest records dataset/fixture/code hashes, selected IDs,
requested model and temperature; traces record prompts, raw answers and returned
model metadata. The changed llm.py hash identifies this prompt revision.

```sh
cd /Users/yanghede/Downloads/CSE291A-Project5

python3 run_clean_audit.py --path support_cases_unique40.jsonl --llm openai --case BASE-0003-NONE --output-root results/helper_scope_v3_targeted
python3 run_clean_audit.py --path support_cases_unique40.jsonl --llm openai --case BASE-0004-NONE --output-root results/helper_scope_v3_targeted
python3 run_clean_audit.py --path support_cases_unique40.jsonl --llm openai --case BASE-0007-NONE --output-root results/helper_scope_v3_targeted

python3 run_clean_audit.py --path support_cases_unique40.jsonl --llm openai --output-root results/helper_scope_v3_full
```

Retain every attempted run and failure; do not rerun until a favorable answer
appears. Inspect the three targeted results before proceeding to the full run.
Do not mix v2 and v3 results or infer 40-case accuracy from targeted samples.

## Preservation and acceptance

Historical datasets, fixtures, logs, answers, summaries, agent reviews and human
scores are preserved. This is a new prompt baseline, not a correction to old
outputs. No commits or paid calls were made. The scoring rubric is unchanged.

Human review must confirm every expected issue is adequately addressed, answers
remain faithful to their assigned records and required steps, and no answer
requires a new ticket for an included issue or claims whole-case completion from
partial evidence. A scoped statement such as “this technical fix does not address
billing” is not automatically a failure; evaluate the full context using the
frozen rubric. Helpers need not repeat each other's answers. Report structural
checks separately from semantic review; even 40/40 structural passes do not
establish task success. Manual acceptance is required before fault experiments.

QA semantic verification, QA-corruption activation, stale dataset defaults and
restart/recovery policies remain separate follow-ups. Prompt hardening may change
attack behavior, so fault comparisons must use the matching new clean baseline.
