from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from core.artifact import artifact_source, tool_event_source
from core.model_client import StructuredModelClient
from core.trace import TraceLogger
from core.workflow import Workflow, WorkflowResult
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

        order_context, order_event_id = tools.get_order_context(task_id)

        inventory_input, inventory_event_id = tools.get_inventory_inputs(task_id)
        inventory_artifact = self.agents.inventory.run(
            payload=inventory_input,
            logger=logger,
            sources=[tool_event_source(inventory_event_id)],
        )

        pricing_input, pricing_event_id = tools.get_pricing_inputs(task_id)
        pricing_artifact = self.agents.pricing.run(
            payload=pricing_input,
            logger=logger,
            sources=[tool_event_source(pricing_event_id)],
        )

        shipping_input, shipping_event_id = tools.get_shipping_inputs(task_id)
        shipping_artifact = self.agents.shipping.run(
            payload=shipping_input,
            logger=logger,
            sources=[tool_event_source(shipping_event_id)],
        )

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

        execution = ExecutionDecision.model_validate(executor_artifact.value)
        for action in execution.actions:
            tools.execute_action(
                action,
                triggered_by_artifact_id=executor_artifact.artifact_id,
            )

        check = check_fulfillment_run(
            order_id=task_id,
            dataset=self.dataset,
            initial_state=initial_state,
            final_state=state,
            inventory_artifact=inventory_artifact,
            pricing_artifact=pricing_artifact,
            shipping_artifact=shipping_artifact,
            plan_artifact=plan_artifact,
            executor_artifact=executor_artifact,
        )

        logger.log(
            "workflow_completed",
            data={
                "outcome": state.order_status,
                "check_passed": check.passed,
                "check_errors": list(check.errors),
                "final_state": state.snapshot(),
            },
            parent_ids=[executor_artifact.artifact_id],
        )

        return WorkflowResult(
            workflow=self.name,
            task_id=task_id,
            run_id=logger.run_id,
            outcome=state.order_status,
            artifacts=(
                inventory_artifact,
                pricing_artifact,
                shipping_artifact,
                plan_artifact,
                executor_artifact,
            ),
            check=check,
            log_path=str(logger.path),
        )
