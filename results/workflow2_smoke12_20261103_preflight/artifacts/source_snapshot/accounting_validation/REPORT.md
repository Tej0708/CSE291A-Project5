# Cost accounting validation

Base HEAD: `9c6532ff7630fa69e30e1a3780fb24136d787ed0`.
Working branch: `codex/workflow2-cost-accounting`.
Workflow 1 reference HEAD: `83cda0815655078936424000f2aa5d4332ef1f3b`.
Metrics schema: `support-cost-v2`. Recovery policy: unchanged `support-recovery-v1`.

- 51 workflow/accounting tests passed, including the frozen formal manifest checks.
- 9 review-tool tests passed with local loopback permission for the HTTP fixture.
- 1,339 before/after pairs matched the immutable base implementation: 1,200
  complete matrix pairs (200 cases x 3 modes x scripted/rule inputs), 135 budget
  boundary pairs (five cases x three modes x three budgets x three limits), and
  four persistent verifier failure/rejection pairs.
- Comparisons check exact prompts, routing decisions, fault boundaries and
  mutations, retry/restart counts, budget counters and blocked stopping points,
  attempt statuses, issue states, histories and quality fields. Measured timing
  is excluded because instrumentation adds overhead.
- The small accounting fixtures cover clean execution, accepted retry, repeated
  rejection, verifier execution failure, successful/failed restart, blocked
  dispatch, failed/missing/incomplete provider usage, nested reference reads,
  overlapping/nested intervals and multiple discard reasons on one call ID.
- Mocked provider tests verify identical original call arguments and outputs,
  unmodified SDK object/retry settings, nullable fields and retained response
  usage when subsequent local response parsing fails.

Preservation checks compare Git blob hashes for all 410 pre-existing tracked
files: 409 unchanged; only csa_workflow/recovery.py changed. In particular llm.py,
prompts, data, services, fault logic, scoring rules, original configuration,
RECOVERY_BASELINES.md, RECOVERY_VALIDATION.md, historical 0/40 results and frozen
experiment files are unchanged. See preservation.json for the complete inventory.
The user's original checkout and its pre-existing modifications were not edited.

An initial test run correctly rejected an edit to frozen llm.py. The final design
restores it byte-for-byte and uses the separate provider_accounting adapter. No
frozen hashes or assertions were relaxed. The HTTP test initially lacked local
loopback access; it passed with that permission. Final test outputs are saved here.

example_log.json is a new English scripted fixture from the modified runner,
not a historical recomputation or paid experiment. Scripted model usage stays
unknown rather than being replaced with fabricated provider tokens. The log
includes source hashes, budget configuration, linked calls/artifacts/recoveries,
all attempts and terminal metrics. COST_ACCOUNTING.md defines its fields and
lists historical metrics that can and cannot be recomputed.

All changed/new text files were scanned for Chinese characters; none were found
(see english_scan.json). No paid experiments or real model API calls were run.
Only the existing review UI test uses local loopback. No merge or push was made.
