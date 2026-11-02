# Phase 1 progress: first inventory workflow

Working branch: `codex/phase1-fulfillment-steps`, based on `order-fulfillment-nk`.
Scope: Idea 2, first workflow (order fulfillment). Completed steps are recorded in separate local commits.

Work proceeds one recommended step at a time. Stop at each checkpoint and report changes,
API usage, findings, and the next step. Use `api-glm-5.3-flash`, one pilot repetition, and
preserve the $50-per-key budget. Offline tests use fake models and spend no API credits.

## Completed foundation and audit

- Reviewed the available branches and course/project documents. `order-fulfillment-nk`
  contains the fulfillment foundation; `main`, `Billing_loop_structure`, and `tej-dev`
  concern the support workflow. `main` and `Billing_loop_structure` have identical trees.
- Confirmed the attached workbook's 13 sheets match `data/dataset.json` after normalizing
  spreadsheet types. The fulfillment dataset contains 30 orders, expected to yield
  18 approvals and 12 stock rejections when each starts from the fixed inventory snapshot.
- Step 1 complete: preserve failed calls, raw responses, partial business state, dependency
  records, and terminal results. Unknown provider usage is never represented as zero.

## Step 1 checkpoint

Failure tracing and terminal results are complete. Offline validation covers all 30 clean
cases, stock-reservation failure, partial state, model timeout, and invalid model JSON.

Next: Step 2, one clean pilot repetition with bounded API spending and saved usage.
No fault or recovery experiments are included in this commit.
