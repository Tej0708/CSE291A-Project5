# Implementation and validation notes

All changes are confined to this new analysis directory. Original experiments, frozen configurations and previous human-review evidence are unchanged. No commit or push is performed for this evaluation.

## Judge selection and pilot

The authenticated key does not expose gpt-6-luna. After the user explicitly authorized an available model, api-glm-5.3-flash was selected using the live accessible-model list and TritonAI public tariff. It shares the model family/name used for original answers, so this is not an independent-model benchmark.

The initial 4,000-token pilot required two local adapter corrections: count cached/created-cache tokens as subsets of prompt usage without applying a discount, and permit exact evidence pointers to supplied root expected_issues/execution_completed fields. Neither correction relaxes exact quote/value checks. Saved responses were reconciled without repeating those calls. CACHE_ACCOUNTING.md retains details.

Two requests exhausted the original 4,000-token cap. GLM documentation indicates forced thinking for GLM-5.3-Flash. The output cap was revised to 12,000 total generated tokens; the prior configuration, code and four valid judgments were archived. All six earlier requests remain in the same ledger. A fresh 10-context pilot passed before full dispatch; pilot_inspection.json records automated pipeline inspection, not human quality approval.

## Execution and cost controls

Four HTTP requests can be in flight. One process holds the file lock throughout execution; a thread mutex serializes durable reservations, usage settlement, response/judgment writes and checkpoint reports. Each reservation includes full catalog input capacity and capped output. Pending reservations count against the ceiling immediately. HTTP/SDK automatic retries are disabled. A fatal unresolved-usage error stops new dispatch; already in-flight calls finish and are accounted. Each job/configuration allows at most two explicit retries on later invocation. Responses with schema, quote, field-identity or aggregation errors remain evaluation errors until a subsequent valid assessment exists.

All configurations share the same $3 ledger and $1 unspent holdback. Historical configurations are explicitly hash-registered. Every request stores its complete payload and hash. Old judgments are not silently reused after a configuration change. Tariff-derived cost conservatively charges cached prompt tokens at the full input rate. Published tariff accounting is not a guarantee about unobservable provider invoice categories.

## Offline validation

The 30 unit tests cover evidence/schema constraints, aggregation, cost accounting, unknown usage, resume and access gates. check_concurrency.py simulates 12 requests without network access and verifies unique persistent reservations and complete settlements. Test locks use temporary directories so tests cannot interfere with an active evaluation lock.

build_results.py joins valid LLM assessments to the prior deterministic measurements, preserving all 240 denominators and exact case/control pairings. It produces contextual review sheets and a triage list without changing human fields. validate_delivery.py verifies original hashes, request/configuration identities, saved evidence, ledger recomputation, human fields and absence of the configured API key in deliverables. Validation output is recorded only after the live run stops.

## Deterministic aggregate repair

`derive_aggregates.py` can recover a response whose only inconsistency is its overall verdict. It recomputes that field using the repository's existing `aggregate(criteria, context)` rule and then runs the unchanged strict validator. Criterion labels, explanations, exact quotes, source values, omissions and follow-up flags are not edited. A response with any other schema/evidence problem is still rejected. `local_aggregation_audit.json` preserves the original overall label, the derived label and request identity. Raw response files remain unchanged. This implements local rule-based aggregation rather than asking the LLM to determine how its own labels combine.
