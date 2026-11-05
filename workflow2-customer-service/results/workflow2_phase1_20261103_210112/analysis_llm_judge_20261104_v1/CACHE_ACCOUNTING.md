# Cache accounting reconciliation

The first response reported 4,139 prompt tokens, including 2,304 created-cache tokens, and 1,002 completion tokens (including 130 reasoning tokens). It was initially held at its full $0.077 reservation while metadata was checked.

The authenticated /model/info reports input $0.15/M, output $0.50/M, cache-read $0.04/M, and no distinct cache-creation or reasoning rate. The published LiteLLM costing documentation explains that token subcategories use their configured rate or text rate when absent. This ledger conservatively charges every prompt token at the full input price, including cache reads/writes; it takes no caching discount. Cache detail counts are validated as subsets of prompt_tokens; completion reasoning is counted within completion_tokens. This is not a claim that cache usage is zero.

Source metadata: selected_model_billing_metadata.json. Costing semantics: https://docs.litellm.ai/docs/proxy/model_cost_map . The prior strict failure and response are preserved; the response is reconciled locally without a second API call.

A separate validation fix accepts a JSON pointer to the entire /expected_issues array, as the prompt already permits; values still must match the supplied input exactly. No criterion or evidence rule was relaxed.

A second adapter correction permits /execution_completed, an actual supplied bundle field required by the documented run aggregation. Its exact boolean value remains validated; the saved second response is reused without another paid call.
