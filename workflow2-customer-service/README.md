# Workflow 2 — Customer-Service Billing Workflow

A multi-agent customer-support workflow used to study how faults propagate
through agent-to-agent handoffs and how different recovery strategies respond.
It is one of the two workflows in the CSE 291A failure-propagation project; see
the [top-level README](../README.md) for the overall methodology.

## What this workflow is

A bounded support loop decomposes a free-text customer request into one or more
issues, resolves each issue with a specialized helper, and checks the result
before closing out:

```
Router → (Technical | Billing) Helper → QA → Router → …
```

- **Router** decomposes the user query into taxonomy issues and, on each turn,
  picks the next unresolved issue to route. It trusts QA feedback verbatim (no
  recovery), which is what lets a corrupted hint misdirect the loop.
- **Technical / Billing helpers** answer a single issue using scenario-specific
  simulated tool records ([csa_workflow/scenario_records.json](csa_workflow/scenario_records.json)).
  Unsupported issues return `unavailable` rather than an unrelated generic record.
- **QA** checks whether each expected issue is resolved with supporting
  evidence, validates its own label shape, and emits feedback back to the Router.

The agents are **deterministic (rule-based) by default** so the harness isolates
*fault behavior* from model variance. An LLM backend (OpenAI) can be dropped in
without changing the orchestration contract. The only guard against an infinite
loop is the per-case iteration budget.

Key modules live in [csa_workflow/](csa_workflow/):

| File | Responsibility |
| --- | --- |
| [orchestrator.py](csa_workflow/orchestrator.py) | Wires the Router → Helper → QA loop with the fault injector on stage boundaries |
| [agents.py](csa_workflow/agents.py) | Router, Technical, Billing, and QA agents |
| [faults.py](csa_workflow/faults.py) | Fault-injector middleware for the five fault types |
| [recovery.py](csa_workflow/recovery.py) | Opt-in recovery runner (unprotected / full-restart / always-verify) |
| [taxonomy.py](csa_workflow/taxonomy.py) | 10 issue types → 2 helper routes, plus Router keyword cues |
| [services.py](csa_workflow/services.py) | Simulated tool records / scenario lookup |
| [state.py](csa_workflow/state.py) | Per-issue ledger and workflow state |
| [dataset.py](csa_workflow/dataset.py) | Loader for the support-case dataset |

## Dataset

[support_cases_unique40.jsonl](support_cases_unique40.jsonl) holds **200
records**: 40 distinct base requests × 5 fault conditions. Each case records the
expected issues, routing, final status, iteration budget, invariants, and the
fault configuration. The 10 issue types route to two helpers:

- **Technical:** `installation_failure`, `login_failure`, `password_reset`,
  `app_crash`, `sync_failure`
- **Billing:** `subscription_status`, `charge_after_cancellation`,
  `duplicate_charge`, `incorrect_invoice`, `refund_status`

## Fault model

Faults are injected as passive middleware that mutates a stage's output *before*
the next agent consumes it. Five fault types, matching the dataset conditions:

| Fault type | Injection point | Effect |
| --- | --- | --- |
| `none` | — | Clean control run |
| `qa_corruption` | QA → Router feedback | Rewrites the `missing_issue` hint to misdirect the Router |
| `helper_corruption` | Helper output | Corrupts a helper's answer/record |
| `timeout` | Simulated tool call | Tool returns `timeout` instead of a record |
| `prompt_injection` | Retrieved support text | Appends an adversarial payload to retrieved content |

## Recovery policies

The opt-in recovery runner compares three execution strategies against the clean
baseline, all under the same one-effective-mutation-per-run fault model:

- **`unprotected`** — fault-injected execution with no corrective intervention.
- **`full_restart`** — restart the workflow after a fault is detected.
- **`always_verify`** — validate intermediate outputs before downstream use.

## Experiments we ran

All experiments are **offline / scripted by default**; live model execution is
opt-in and gated behind explicit flags and manifest verification.

| Experiment | Script | What it does |
| --- | --- | --- |
| **Clean baseline audit** | [run_clean_audit.py](run_clean_audit.py) | Records the clean workflow (routing, prompts, responses, tokens, QA feedback, durations, hashes) without changing agent decisions. |
| **Fault activation audit** | [run_fault_audit.py](run_fault_audit.py) | Confirms each fault hook actually activates and is consumed downstream — activation evidence, never recovery scoring. |
| **Step 3 live pilot** | [run_live_pilot.py](run_live_pilot.py) | Bounded live pilot on a frozen case selection; produced the activation/continuation findings (not full-restart recovery). |
| **Formal QA-corruption study** | [run_formal_experiment.py](run_formal_experiment.py) | Frozen 40-run paired experiment (20 clean + 20 `qa_first_missing_once_v1`), with a dedicated observer, manifest hashes, and offline metric/quality evaluation. |
| **Recovery smoke pilot** | [run_recovery_smoke_pilot.py](run_recovery_smoke_pilot.py) | Bounded 12-run smoke test (BASE-0004 × 4 conditions × 3 policies) exercising the recovery runner with budget/USD gates. |
| **Phase 1 full experiment** | [workflow2_phase1.py](workflow2_phase1.py) + [phase1_metrics.py](phase1_metrics.py) | Full applicability → prepare → execute → analyze pipeline across all scenarios and policies; evidence-only metric reduction. |

Results are written to timestamped directories under [results/](results/). The
formal-experiment contracts (logging schema, metrics, and quality rules) are
documented in [TEAM_HANDOFF.md](TEAM_HANDOFF.md),
[BASELINE_EVALUATION_RULES.md](BASELINE_EVALUATION_RULES.md), and
[formal_experiment/PLAN.md](formal_experiment/PLAN.md).

> Scope note: `qa_corruption` activation causes repeated work followed by
> continuation to unresolved work — this is *not* full-restart recovery. Ledger
> completion is a control-flow/evidence status, not verified answer correctness.

## Useful commands

Run everything from the repository root with the project virtual environment.
`PYTHONDONTWRITEBYTECODE=1` keeps the tree clean. Output directories must be new.

### Clean baseline audit

```sh
# Rule-based (no model calls)
.venv/bin/python run_clean_audit.py --path support_cases_unique40.jsonl --llm none
# Live OpenAI backend (reads .env), single case
.venv/bin/python run_clean_audit.py --path support_cases_unique40.jsonl --llm openai --case BASE-0022-NONE
```

### Fault activation audit

```sh
.venv/bin/python run_fault_audit.py --backend rule --output results/fault_audit_$(date +%Y%m%d_%H%M%S)
.venv/bin/python run_fault_audit.py --fault qa_corruption --profile qa_first_missing_once_v1 \
  --output results/fault_audit_qa_$(date +%Y%m%d_%H%M%S)
```

### Formal QA-corruption study

```sh
.venv/bin/python run_formal_experiment.py prepare                         # build/refresh the frozen manifest
.venv/bin/python run_formal_experiment.py verify                          # check nothing frozen has changed
.venv/bin/python run_formal_experiment.py execute --output results/workflow2_formal_$(date +%Y%m%d_%H%M%S)
.venv/bin/python run_formal_experiment.py evaluate --run-dir <run-dir> --output <run-dir>/metrics
```

`execute` makes live provider calls — run only after `verify` passes and the run
is authorized. Editing any frozen file intentionally makes `verify` fail.

### Recovery smoke pilot

```sh
# Offline preparation (no network)
.venv/bin/python run_recovery_smoke_pilot.py --output results/workflow2_recovery_smoke_prep_$(date +%Y%m%d_%H%M%S)
# Live execution (reads .env); an optional verified pricing config enables the USD gate
.venv/bin/python run_recovery_smoke_pilot.py --execute \
  --output results/workflow2_recovery_smoke_local_$(date +%Y%m%d_%H%M%S)
```

### Phase 1 full experiment

```sh
.venv/bin/python workflow2_phase1.py applicability --output results/phase1_applicability.json
.venv/bin/python workflow2_phase1.py prepare  --config <config.json> --output results/phase1_manifest.json
.venv/bin/python workflow2_phase1.py execute  --manifest results/phase1_manifest.json --output results/workflow2_phase1_$(date +%Y%m%d_%H%M%S)
.venv/bin/python workflow2_phase1.py analyze  --run-dir <run-dir> --output <run-dir>/analysis.json
```

### Tests

```sh
# All workflow tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -v
# Review-tool tests (needs local loopback permission for the HTTP test)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s human_review_tool -p 'test_*.py' -v
# A single suite
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest test_recovery_smoke_pilot -q
```

## Repository layout

```
csa_workflow/                  Core workflow: agents, orchestrator, faults, recovery, taxonomy
formal_experiment/             Frozen formal study: manifest, schemas, PLAN.md, REPORT.md
human_review_tool/             Offline draft-review app and tests
results/                       Timestamped experiment outputs (traces, metrics, answers)
support_cases_unique40.jsonl   Dataset: 40 base requests × 5 fault conditions
run_clean_audit.py             Clean baseline audit
run_fault_audit.py             Fault activation audit
run_live_pilot.py              Bounded Step 3 live pilot
run_formal_experiment.py       Formal QA-corruption study (prepare/verify/execute/evaluate)
run_recovery_smoke_pilot.py    Recovery smoke pilot (unprotected/full_restart/always_verify)
workflow2_phase1.py            Phase 1 pipeline (applicability/prepare/execute/analyze)
phase1_metrics.py              Evidence-only Phase 1 metric reduction
test_*.py                      Offline regression suites
```

## Related docs

- [TEAM_HANDOFF.md](TEAM_HANDOFF.md) — logging schema and metrics contracts
- [BASELINE_EVALUATION_RULES.md](BASELINE_EVALUATION_RULES.md) — frozen answer-quality rubric
- [formal_experiment/PLAN.md](formal_experiment/PLAN.md) — formal-study protocol and reproducible commands
- [RECOVERY_SMOKE_PILOT.md](RECOVERY_SMOKE_PILOT.md) — recovery smoke-pilot details
- [WORKFLOW2_HANDOFF.md](WORKFLOW2_HANDOFF.md) — earlier milestone handoff
