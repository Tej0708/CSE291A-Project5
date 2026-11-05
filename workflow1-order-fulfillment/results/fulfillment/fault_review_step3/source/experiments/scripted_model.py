from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel

from core.model_client import ModelResult, ModelUsage
from workflows.fulfillment.models import (
    ExecutionDecision,
    FulfillmentPlan,
    InventoryResult,
    PricingResult,
    ShippingResult,
)


CENT = Decimal("0.01")


def money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


class ScriptedModelClient:
    """Offline rule-following stand-in. Does not interpret text instructions or call an API."""

    def generate(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> ModelResult:
        del system_prompt

        if output_schema is InventoryResult:
            value = self._inventory(payload)
        elif output_schema is PricingResult:
            value = self._pricing(payload)
        elif output_schema is ShippingResult:
            value = self._shipping(payload)
        elif output_schema is FulfillmentPlan:
            value = self._plan(payload)
        elif output_schema is ExecutionDecision:
            value = self._executor(payload)
        else:
            raise AssertionError(f"Unexpected schema: {output_schema}")

        validated = output_schema.model_validate(value)
        return ModelResult(
            value=validated,
            raw_text=json.dumps(value),
            usage=ModelUsage(),
            latency_ms=0.1,
            model_name="fake-model",
        )

    @staticmethod
    def _inventory(payload: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for item in payload["items"]:
            sufficient = item["available_qty"] >= item["requested_qty"]
            rows.append(
                {
                    "product_id": item["product_id"],
                    "requested_qty": item["requested_qty"],
                    "available_qty": item["available_qty"],
                    "sufficient": sufficient,
                }
            )
        return {
            "items": rows,
            "all_items_available": all(row["sufficient"] for row in rows),
        }

    @staticmethod
    def _pricing(payload: dict[str, Any]) -> dict[str, Any]:
        rows = []
        subtotal = Decimal("0")
        for item in payload["items"]:
            line_total = (
                Decimal(str(item["quantity"]))
                * Decimal(str(item["unit_price_usd"]))
            )
            subtotal += line_total
            rows.append(
                {
                    "product_id": item["product_id"],
                    "quantity": item["quantity"],
                    "unit_price_usd": item["unit_price_usd"],
                    "line_total_usd": money(line_total),
                }
            )
        return {"items": rows, "subtotal_usd": money(subtotal)}

    @staticmethod
    def _shipping(payload: dict[str, Any]) -> dict[str, Any]:
        total_weight = sum(
            item["quantity"] * item["unit_weight_kg"]
            for item in payload["items"]
        )
        rate = payload["rate"]
        cost = (
            Decimal(str(rate["base_price_usd"]))
            + Decimal(str(rate["price_per_kg_usd"]))
            * Decimal(str(total_weight))
        )
        return {
            "zone": payload["zone"],
            "service": payload["service"],
            "total_weight_kg": total_weight,
            "shipping_cost_usd": money(cost),
            "max_weight_kg": rate["max_weight_kg"],
            "within_weight_limit": total_weight <= rate["max_weight_kg"],
            "estimated_days": rate["estimated_days"],
        }

    @staticmethod
    def _plan(payload: dict[str, Any]) -> dict[str, Any]:
        inventory = payload["inventory"]
        pricing = payload["pricing"]
        shipping = payload["shipping"]
        order = payload["order"]

        if not inventory["all_items_available"] or not shipping["within_weight_limit"]:
            return {
                "order_id": order["order_id"],
                "decision": ("reject_insufficient_stock" if not inventory["all_items_available"]
                             else "reject_shipping_constraint"),
                "reason": "Inventory or shipping constraint failed.",
                "subtotal_usd": pricing["subtotal_usd"],
                "shipping_service": None,
                "total_weight_kg": None,
                "shipping_usd": None,
                "total_usd": None,
            }

        total = money(
            Decimal(str(pricing["subtotal_usd"]))
            + Decimal(str(shipping["shipping_cost_usd"]))
        )
        return {
            "order_id": order["order_id"],
            "decision": "approve_fulfillment",
            "reason": "All items are available.",
            "subtotal_usd": pricing["subtotal_usd"],
            "shipping_service": shipping["service"],
            "total_weight_kg": shipping["total_weight_kg"],
            "shipping_usd": shipping["shipping_cost_usd"],
            "total_usd": total,
        }

    @staticmethod
    def _executor(payload: dict[str, Any]) -> dict[str, Any]:
        plan = payload["plan"]
        if plan["decision"] != "approve_fulfillment":
            return {
                "actions": [
                    {
                        "tool": "update_order_status",
                        "status": plan["decision"].replace("reject_", "rejected_", 1),
                    }
                ]
            }

        items = payload["order"]["items"]
        return {
            "actions": [
                {
                    "tool": "reserve_inventory",
                    "items": [
                        {
                            "product_id": item["product_id"],
                            "quantity": item["quantity"],
                        }
                        for item in items
                    ],
                },
                {
                    "tool": "create_shipment",
                    "shipping_service": plan["shipping_service"],
                    "shipping_cost_usd": plan["shipping_usd"],
                    "total_weight_kg": plan["total_weight_kg"],
                },
                {
                    "tool": "update_order_status",
                    "status": "fulfilled",
                },
            ]
        }

