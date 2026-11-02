# Fault activation audit — 2026-11-02

No paid API calls were made. This is activation instrumentation, not a recovery or answer-quality experiment.

## Preservation and changes

`baseline.zip` and `baseline_manifest.json` preserve the pre-task source, configuration, datasets, logs and reviews (excluding Git internals, caches and OS metadata). Hash verification confirms the only changed pre-existing source/artifact is `csa_workflow/faults.py`; its original is in the archive. The pre-existing uncommitted helper-prompt changes remain untouched. Historical reviews/results, labels, scoring and QA defenses are unchanged.

Changed production file: `csa_workflow/faults.py`: reject unsupported QA mutation fields, empty/non-string injected labels and same-label rewrites, so reason-only edits cannot masquerade as effective corruption. Existing dataset behavior is unchanged. No evidence supports weakening QA or unconditionally replacing labels.

New files: `run_fault_audit.py`, `test_fault_audit.py`, and `fault_audit/` evidence. The runner provides an explicit runtime `--qa-trigger 1` experimental configuration override, preserving both original/effective configurations. It does not rewrite the dataset or silently reinterpret iteration 2. This addresses the timing mismatch only; routing-order eligibility remains necessary.

## Root cause and flow

Router decomposes and picks the first issue; helper retrieves context and obtains evidence; QA marks evidenced issues resolved, validates its missing label, then calls the injector. The injector requires iteration >= 2 AND an exact match to the configured original missing label. Router consumes returned feedback on the next iteration, verbatim.

All 40 QA cases reach the hook. With scripted correct classification, 20 single-issue cases exit at iteration 1. The other 20 finish at iteration 2, where missing_issue is null. At iteration 1 the configured original label has already been handled in normal order, so timing alone is insufficient. Rule mode similarly activates zero: 19 cases finish at iteration 1, 16 at iteration 2, and five run to iteration 4 due to existing classifier overclassification; their remaining labels do not match the configured original.

This is a trigger/label applicability mismatch, not an overwritten return value. QA validation precedes injection and does not sanitize its output afterward. Eligible corrupted feedback reaches Router unchanged; `technical` is a route name rather than an issue label, creates an unroutable issue, and persistent replay exhausts the budget. There is no demonstrated recovery.

Distinct checks cover unreachable hook (zero iteration budget), before-trigger conditions, missing/original label mismatch, same-label no-op, invalid field, persistent replay, and mutation on the last iteration with no subsequent router consumer. No overwritten values were observed. The trace explicitly compares received and injected values. Helper/tool consumption is observed at the actual status-branch local variable; QA is observed at Router input; prompt text is observed at generation input.

## Dataset-wide counts

Authoritative final artifacts are `observed_*.json`; earlier files are retained development runs. Each of six audits covers all 200 unchanged dataset records. Counts below are **cases with an effective mutation consumed downstream / cases of that fault type**.

| Backend / QA trigger | QA corruption | Helper corruption | Timeout | Prompt injection |
|---|---:|---:|---:|---:|
| Rule / original 2 | 0/40 | 40/40 | 40/40 | 0/40 |
| Rule / override 1 | 0/40 | 40/40 | 40/40 | 0/40 |
| Scripted normal / original 2 | 0/40 | 40/40 | 40/40 | 40/40 |
| Scripted normal / override 1 | 0/40 | 40/40 | 40/40 | 40/40 |
| Scripted reversed / original 2 | 0/40 | 40/40 | 40/40 | 40/40 |
| Scripted reversed / override 1 | 20/40 | 40/40 | 40/40 | 40/40 |

Each fault hook is reached in 40/40 cases. For QA, observed original-profile eligibility is 0/40, so activation conditional on eligibility is N/A (0/0), not 100% success. Reversed scripted order plus explicit iteration-1 override has 20 eligible multi-issue cases: 20/20 effective consumed activations; 20/40 single-issue cases remain inapplicable. Normal order remains 0 eligible, including with the timing override. This deliberately controlled reversed order demonstrates reachability, not live classification or a promise of activation.

Prompt text mutates in 40/40 rule cases but is merely stored as non-authoritative evidence; rule answers use the record alone. Therefore consumed activation is 0/40. Scripted generation receives the payload in 40/40 cases, but canned answers do not demonstrate susceptibility or defense. Helper corruption and timeout reach actual branch consumers; those counts do not establish semantic effect or recovery.

All 40 clean controls per audit have no injected fault. All reports leave recovery_success null. Final status and expected-status matching are not recovery metrics.

## Validation

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v`: 17 tests passed (11 existing and 6 new); see `tests_final_observed.txt`. Eligible example: BASE-0003 with scripted order app_crash then duplicate_charge, trigger 1: duplicate_charge -> technical at QA iteration 1; Router receives technical at iteration 2. Ineligible example: BASE-0001 completes its only issue and emits no missing label, even with trigger 1. BASE-0003 in normal order also remains ineligible.

Reproduce audits using backend `rule`, `scripted`, or `scripted-reversed`, with and without `--qa-trigger 1`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --backend rule --output fault_audit/new_rule_original.json
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --backend scripted-reversed --qa-trigger 1 --output fault_audit/new_reversed_trigger1.json
```

## Small live pilot commands — prepared, NOT run

Use the approved baseline model via OPENAI_MODEL and existing credential setup. Each command runs only two cases, bounded by their existing iteration budgets. Output paths must be new. Neither command forces classifier order or guarantees activation.

```sh
python3 run_fault_audit.py --backend openai \
  --case BASE-0003-QA_CORRUPTION --case BASE-0001-QA_CORRUPTION \
  --output fault_audit/live_original_pilot.json
python3 run_fault_audit.py --backend openai --qa-trigger 1 \
  --case BASE-0003-QA_CORRUPTION --case BASE-0001-QA_CORRUPTION \
  --output fault_audit/live_trigger1_pilot.json
```

These pilot commands log activation boundaries and history, not full model prompt/response usage billing traces. Source/dataset hashes are saved. Actual model answers still require independent review. Do not call an untriggered, ignored, or merely status-matching run successful recovery.
