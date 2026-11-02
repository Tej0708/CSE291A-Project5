"""Post-run evaluation; gold labels are only accessed here."""
from core.workflow import CheckResult
from .validation import STAGES, differences, final_state_errors, reference_artifacts


def assess_run(*, order_id, dataset, initial_state, final_state, artifacts):
    reference = reference_artifacts(dataset, initial_state, order_id)
    by_stage = {artifact.stage: artifact for artifact in artifacts}
    stage_checks = {}
    for stage in STAGES:
        errors = (differences(by_stage[stage].value, reference[stage]) if stage in by_stage
                  else ['Stage did not complete'])
        stage_checks[stage] = CheckResult(not errors, tuple(errors))
    truth = dataset.get_ground_truth(order_id)
    oracle = {'decision': truth.expected_decision, 'subtotal_usd': truth.expected_subtotal_usd,
              'shipping_usd': truth.expected_shipping_usd, 'total_usd': truth.expected_total_usd}
    oracle_errors = differences({key: reference['planning_agent'][key] for key in oracle}, oracle)
    state_errors = final_state_errors(dataset, initial_state, final_state, order_id)
    task_errors = list(stage_checks['planning_agent'].errors) + state_errors + oracle_errors
    all_errors = [f'{stage}: {error}' for stage, check in stage_checks.items() for error in check.errors]
    all_errors += state_errors + oracle_errors
    return (CheckResult(not all_errors, tuple(all_errors)),
            CheckResult(not task_errors, tuple(task_errors)), stage_checks)


def check_fulfillment_run(*, order_id, dataset, initial_state, final_state,
                          inventory_artifact, pricing_artifact, shipping_artifact,
                          plan_artifact, executor_artifact):
    """Compatibility entry point for complete executions."""
    return assess_run(order_id=order_id, dataset=dataset, initial_state=initial_state,
                      final_state=final_state, artifacts=[inventory_artifact, pricing_artifact,
                      shipping_artifact, plan_artifact, executor_artifact])[0]
