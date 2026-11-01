from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from core.artifact import AgentArtifact
from core.workflow import CheckResult

from .dataset import FulfillmentDataset
from .models import (
    ExecutionDecision,
    FulfillmentPlan,
    InventoryResult,
    PricingResult,
    ShippingResult,
)
from .state import FulfillmentState


CENT = Decimal("0.01")


def _rounded(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))


def _close(left: float | None, right: float | None, tolerance: float = 0.01) -> bool:
    if left is None or right is None:
        return left is right
    return abs(left - right) <= tolerance


def check_fulfillment_run(
    *,
    order_id: str,
    dataset: FulfillmentDataset,
    initial_state: FulfillmentState,
    final_state: FulfillmentState,
    inventory_artifact: AgentArtifact,
    pricing_artifact: AgentArtifact,
    shipping_artifact: AgentArtifact,
    plan_artifact: AgentArtifact,
    executor_artifact: AgentArtifact,
) -> CheckResult:
    """Validate a fulfillment run independently from the LLM outputs."""
    errors: list[str] = []

    inventory = InventoryResult.model_validate(inventory_artifact.value)
    pricing = PricingResult.model_validate(pricing_artifact.value)
    shipping = ShippingResult.model_validate(shipping_artifact.value)
    plan = FulfillmentPlan.model_validate(plan_artifact.value)
    execution = ExecutionDecision.model_validate(executor_artifact.value)
    truth = dataset.get_ground_truth(order_id)
    order = dataset.get_order(order_id)
    items = dataset.get_order_items(order_id)

    # Inventory artifact
    expected_inventory = {
        item.product_id: (
            item.quantity,
            initial_state.inventory[item.product_id]["available_qty"],
        )
        for item in items
    }
    actual_inventory = {
        item.product_id: (item.requested_qty, item.available_qty, item.sufficient)
        for item in inventory.items
    }

    if set(actual_inventory) != set(expected_inventory):
        errors.append("Inventory Agent returned the wrong product set.")
    else:
        for product_id, (requested, available) in expected_inventory.items():
            actual_requested, actual_available, actual_sufficient = actual_inventory[
                product_id
            ]
            if actual_requested != requested or actual_available != available:
                errors.append(f"Inventory values are wrong for {product_id}.")
            if actual_sufficient != (available >= requested):
                errors.append(f"Inventory sufficiency is wrong for {product_id}.")

    expected_all_available = all(
        available >= requested
        for requested, available in expected_inventory.values()
    )
    if inventory.all_items_available != expected_all_available:
        errors.append("Inventory all_items_available is incorrect.")

    # Pricing artifact
    expected_subtotal = _rounded(
        sum(
            Decimal(str(item.quantity))
            * Decimal(str(item.unit_price_at_purchase_usd))
            for item in items
        )
    )
    if not _close(pricing.subtotal_usd, expected_subtotal):
        errors.append("Pricing subtotal is incorrect.")

    pricing_by_product = {item.product_id: item for item in pricing.items}
    if set(pricing_by_product) != {item.product_id for item in items}:
        errors.append("Pricing Agent returned the wrong product set.")
    else:
        for item in items:
            actual = pricing_by_product[item.product_id]
            expected_line = _rounded(
                Decimal(str(item.quantity))
                * Decimal(str(item.unit_price_at_purchase_usd))
            )
            if actual.quantity != item.quantity:
                errors.append(f"Pricing quantity is wrong for {item.product_id}.")
            if not _close(
                actual.unit_price_usd,
                item.unit_price_at_purchase_usd,
            ):
                errors.append(f"Pricing unit price is wrong for {item.product_id}.")
            if not _close(actual.line_total_usd, expected_line):
                errors.append(f"Pricing line total is wrong for {item.product_id}.")

    # Shipping artifact
    rate = dataset.get_shipping_rate(order.shipping_zone, order.shipping_service)
    expected_weight = sum(
        item.quantity * dataset.get_product(item.product_id).weight_kg
        for item in items
    )
    expected_shipping = _rounded(
        Decimal(str(rate.base_price_usd))
        + Decimal(str(rate.price_per_kg_usd)) * Decimal(str(expected_weight))
    )

    if shipping.zone != order.shipping_zone or shipping.service != order.shipping_service:
        errors.append("Shipping Agent used the wrong zone/service.")
    if abs(shipping.total_weight_kg - expected_weight) > 1e-6:
        errors.append("Shipping total weight is incorrect.")
    if not _close(shipping.shipping_cost_usd, expected_shipping):
        errors.append("Shipping cost is incorrect.")
    if shipping.within_weight_limit != (expected_weight <= rate.max_weight_kg):
        errors.append("Shipping weight-limit decision is incorrect.")

    # Planner artifact and dataset oracle
    if plan.order_id != order_id:
        errors.append("Planner returned the wrong order_id.")
    if plan.decision != truth.expected_decision:
        errors.append(
            f"Planner decision {plan.decision!r} does not match oracle "
            f"{truth.expected_decision!r}."
        )
    if not _close(plan.subtotal_usd, truth.expected_subtotal_usd):
        errors.append("Planner subtotal does not match oracle.")
    if not _close(plan.shipping_usd, truth.expected_shipping_usd):
        errors.append("Planner shipping amount does not match oracle.")
    if not _close(plan.total_usd, truth.expected_total_usd):
        errors.append("Planner total does not match oracle.")

    if plan.decision == "approve_fulfillment":
        if plan.shipping_service != order.shipping_service:
            errors.append("Planner shipping_service is incorrect.")
        if plan.total_weight_kg is None or abs(plan.total_weight_kg - expected_weight) > 1e-6:
            errors.append("Planner total_weight_kg is incorrect.")
    else:
        if any(
            value is not None
            for value in (
                plan.shipping_service,
                plan.total_weight_kg,
                plan.shipping_usd,
                plan.total_usd,
            )
        ):
            errors.append("Rejected plan should not contain shipment/total fields.")

    # Executor output + resulting mutable state
    tool_names = [action.tool for action in execution.actions]
    if truth.expected_decision == "approve_fulfillment":
        if tool_names != [
            "reserve_inventory",
            "create_shipment",
            "update_order_status",
        ]:
            errors.append("Executor action sequence is incorrect for approval.")
        else:
            reserve_action, shipment_action, status_action = execution.actions
            expected_reservation = {
                item.product_id: item.quantity for item in items
            }
            actual_reservation = {
                item.product_id: item.quantity for item in reserve_action.items
            }
            if actual_reservation != expected_reservation:
                errors.append("Executor reservation quantities are incorrect.")
            if shipment_action.shipping_service != order.shipping_service:
                errors.append("Executor shipment service is incorrect.")
            if not _close(shipment_action.shipping_cost_usd, expected_shipping):
                errors.append("Executor shipment cost is incorrect.")
            if abs(shipment_action.total_weight_kg - expected_weight) > 1e-6:
                errors.append("Executor shipment weight is incorrect.")
            if status_action.status != "fulfilled":
                errors.append("Executor final status action is incorrect.")

        if final_state.order_status != "fulfilled":
            errors.append("Approved order did not end in fulfilled status.")
        if order_id not in final_state.reservations:
            errors.append("Approved order did not reserve inventory.")
        if order_id not in final_state.shipments:
            errors.append("Approved order did not create a shipment.")
        else:
            shipment = final_state.shipments[order_id]
            if shipment["shipping_service"] != order.shipping_service:
                errors.append("Final shipment service is incorrect.")
            if not _close(shipment["shipping_cost_usd"], expected_shipping):
                errors.append("Final shipment cost is incorrect.")

        for item in items:
            before = initial_state.inventory[item.product_id]
            after = final_state.inventory[item.product_id]
            if after["available_qty"] != before["available_qty"] - item.quantity:
                errors.append(
                    f"Final available inventory is wrong for {item.product_id}."
                )
            if after["reserved_qty"] != before["reserved_qty"] + item.quantity:
                errors.append(
                    f"Final reserved inventory is wrong for {item.product_id}."
                )
    else:
        if tool_names != ["update_order_status"]:
            errors.append("Executor action sequence is incorrect for rejection.")
        elif execution.actions[0].status != "rejected_insufficient_stock":
            errors.append("Executor rejection status action is incorrect.")
        if final_state.order_status != "rejected_insufficient_stock":
            errors.append("Rejected order has the wrong final status.")
        if final_state.reservations or final_state.shipments:
            errors.append("Rejected order should not reserve inventory or create shipment.")
        if final_state.inventory != initial_state.inventory:
            errors.append("Rejected order should not modify inventory state.")

    return CheckResult(passed=not errors, errors=tuple(errors))
