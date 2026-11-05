from __future__ import annotations

from dataclasses import dataclass

from core.agent import StructuredAgent
from core.model_client import StructuredModelClient

from .models import (
    ExecutionDecision,
    FulfillmentPlan,
    InventoryResult,
    PricingResult,
    ShippingResult,
)


INVENTORY_PROMPT = """
You are the Inventory Agent in an order-fulfillment workflow.
Use only the provided inventory tool data.
For each item, copy product_id, requested_qty, and available_qty, then set
sufficient to whether available_qty >= requested_qty.
Set all_items_available to true only when every item is sufficient.
Do not invent stock values or modify quantities.
""".strip()


PRICING_PROMPT = """
You are the Pricing Agent in an order-fulfillment workflow.
Use the provided purchase-time unit prices, not outside/current prices.
For each line, compute line_total_usd = quantity * unit_price_usd.
Set subtotal_usd to the sum of all line totals.
Round monetary values to two decimal places.
""".strip()


SHIPPING_PROMPT = """
You are the Shipping Agent in an order-fulfillment workflow.
Use only the supplied item weights and shipping-rate record.
Compute total_weight_kg as sum(quantity * unit_weight_kg).
Compute shipping_cost_usd = base_price_usd + price_per_kg_usd * total_weight_kg.
Round shipping_cost_usd to two decimal places.
Set within_weight_limit based on total_weight_kg <= max_weight_kg.
Copy zone, service, max_weight_kg, and estimated_days from the tool data.
""".strip()


PLANNER_PROMPT = """
You are the Planning Agent in an order-fulfillment workflow.
Combine the Inventory, Pricing, and Shipping artifacts into one fulfillment plan.

Rules:
1. If any inventory item is insufficient, decision must be
   reject_insufficient_stock. Keep subtotal_usd, but set shipping_service,
   total_weight_kg, shipping_usd, and total_usd to null.
2. Otherwise, decision must be approve_fulfillment only if shipping is within
   its weight limit. Set shipping fields from the Shipping artifact and set
   total_usd = subtotal_usd + shipping_usd, rounded to two decimals.
3. Explain the decision briefly in reason.
4. Do not change upstream values.
5. If stock is sufficient but shipping exceeds its weight limit, use
   reject_shipping_constraint, keep subtotal_usd, and set all shipment/total fields to null.
""".strip()


EXECUTOR_PROMPT = """
You are the Executor Agent. Translate the approved/rejected fulfillment plan
into an exact ordered list of allowed simulated tool actions.

For approve_fulfillment, output exactly these actions in this order:
1. reserve_inventory, using every order item and its requested quantity
2. create_shipment, using shipping_service, shipping_cost_usd, and
   total_weight_kg from the plan
3. update_order_status with status = fulfilled

For reject_insufficient_stock, output exactly one action:
1. update_order_status with status = rejected_insufficient_stock

For reject_shipping_constraint, output exactly one action:
1. update_order_status with status = rejected_shipping_constraint

Use no other tool names. Do not modify quantities or monetary values.
""".strip()


@dataclass(frozen=True)
class FulfillmentAgents:
    inventory: StructuredAgent
    pricing: StructuredAgent
    shipping: StructuredAgent
    planner: StructuredAgent
    executor: StructuredAgent


def build_agents(model_client: StructuredModelClient) -> FulfillmentAgents:
    workflow = "fulfillment"
    return FulfillmentAgents(
        inventory=StructuredAgent(
            workflow=workflow,
            name="inventory_agent",
            system_prompt=INVENTORY_PROMPT,
            output_schema=InventoryResult,
            model_client=model_client,
        ),
        pricing=StructuredAgent(
            workflow=workflow,
            name="pricing_agent",
            system_prompt=PRICING_PROMPT,
            output_schema=PricingResult,
            model_client=model_client,
        ),
        shipping=StructuredAgent(
            workflow=workflow,
            name="shipping_agent",
            system_prompt=SHIPPING_PROMPT,
            output_schema=ShippingResult,
            model_client=model_client,
        ),
        planner=StructuredAgent(
            workflow=workflow,
            name="planning_agent",
            system_prompt=PLANNER_PROMPT,
            output_schema=FulfillmentPlan,
            model_client=model_client,
        ),
        executor=StructuredAgent(
            workflow=workflow,
            name="executor_agent",
            system_prompt=EXECUTOR_PROMPT,
            output_schema=ExecutionDecision,
            model_client=model_client,
        ),
    )
