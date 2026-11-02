from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from core.artifact import AgentArtifact, artifact_source, tool_event_source
from core.model_client import StructuredModelClient
from core.trace import TraceLogger
from core.workflow import CheckResult, Workflow, WorkflowResult
from data.loader import DEFAULT_DATASET_PATH

from .agents import build_agents
from .checker import check_fulfillment_run
from .dataset import FulfillmentDataset
from .models import ExecutionDecision
from .state import FulfillmentState
from .tools import FulfillmentTools


class FulfillmentWorkflow(Workflow):
    name = "fulfillment"

    def __init__(
        self,
        *,
        model_client: StructuredModelClient,
        dataset_path: str | Path = DEFAULT_DATASET_PATH,
        log_dir: str | Path = "logs",
    ) -> None:
        self.dataset = FulfillmentDataset(dataset_path)
        self.agents = build_agents(model_client)
        self.log_dir = log_dir

    def list_task_ids(self) -> list[str]:
        return self.dataset.list_order_ids()

    def run(self, task_id: str) -> WorkflowResult:
        state = FulfillmentState.from_dataset(self.dataset, task_id)
        initial_state = deepcopy(state)
        logger = TraceLogger(
            workflow=self.name,
            task_id=task_id,
            log_dir=self.log_dir,
        )
        tools = FulfillmentTools(
            dataset=self.dataset,
            state=state,
            logger=logger,
        )

        logger.log(
            "workflow_started",
            data={"initial_state": state.snapshot()},
        )

        artifacts: list[AgentArtifact] = []
        error = error_type = failed_stage = None
        run_status = "completed"
        try:
            self._execute(task_id, tools, logger, artifacts)
            check = check_fulfillment_run(
                order_id=task_id, dataset=self.dataset, initial_state=initial_state,
                final_state=state, inventory_artifact=artifacts[0],
                pricing_artifact=artifacts[1], shipping_artifact=artifacts[2],
                plan_artifact=artifacts[3], executor_artifact=artifacts[4],
            )
        except Exception as exc:
            run_status = "error"
            error, error_type = str(exc), getattr(exc, "error_type", type(exc).__name__)
            failed_stage = logger.last_stage
            check = CheckResult(False, (f"{failed_stage}: {error}",))

        logger.log(
            "workflow_completed", data={
                "outcome": state.order_status, "run_status": run_status,
                "check_passed": check.passed, "check_errors": list(check.errors),
                "failed_stage": failed_stage, "error_type": error_type, "error": error,
                "final_state": state.snapshot(),
            }, parent_ids=[a.artifact_id for a in artifacts[-1:]],
        )
        return WorkflowResult(
            workflow=self.name, task_id=task_id, run_id=logger.run_id,
            outcome=state.order_status, artifacts=tuple(artifacts), check=check,
            log_path=str(logger.path), run_status=run_status, failed_stage=failed_stage,
            error_type=error_type, error=error, initial_state=initial_state.snapshot(),
            final_state=state.snapshot(),
        )

    def _execute(self, task_id: str, tools: FulfillmentTools, logger: TraceLogger,
                 artifacts: list[AgentArtifact]) -> None:
        order_context, order_event_id = tools.get_order_context(task_id)

        inventory_input, inventory_event_id = tools.get_inventory_inputs(task_id)
        inventory_artifact = self.agents.inventory.run(
            payload=inventory_input,
            logger=logger,
            sources=[tool_event_source(inventory_event_id)],
        )
        artifacts.append(inventory_artifact)

        pricing_input, pricing_event_id = tools.get_pricing_inputs(task_id)
        pricing_artifact = self.agents.pricing.run(
            payload=pricing_input,
            logger=logger,
            sources=[tool_event_source(pricing_event_id)],
        )
        artifacts.append(pricing_artifact)

        shipping_input, shipping_event_id = tools.get_shipping_inputs(task_id)
        shipping_artifact = self.agents.shipping.run(
            payload=shipping_input,
            logger=logger,
            sources=[tool_event_source(shipping_event_id)],
        )
        artifacts.append(shipping_artifact)

        plan_artifact = self.agents.planner.run(
            payload={
                "order": order_context["order"],
                "inventory": inventory_artifact.value,
                "pricing": pricing_artifact.value,
                "shipping": shipping_artifact.value,
            },
            logger=logger,
            sources=[
                tool_event_source(order_event_id),
                artifact_source(inventory_artifact),
                artifact_source(pricing_artifact),
                artifact_source(shipping_artifact),
            ],
        )
        artifacts.append(plan_artifact)

        executor_artifact = self.agents.executor.run(
            payload={
                "order": order_context,
                "plan": plan_artifact.value,
            },
            logger=logger,
            sources=[
                tool_event_source(order_event_id),
                artifact_source(plan_artifact),
            ],
        )
        artifacts.append(executor_artifact)

        execution = ExecutionDecision.model_validate(executor_artifact.value)
        for action in execution.actions:
            tools.execute_action(
                action,
                triggered_by_artifact_id=executor_artifact.artifact_id,
            )
