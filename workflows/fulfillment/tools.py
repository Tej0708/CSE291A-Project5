from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
import time

from core.trace import TraceLogger

from .dataset import FulfillmentDataset
from .models import (
    CreateShipmentAction,
    ReserveInventoryAction,
    ToolAction,
    UpdateOrderStatusAction,
)
from .state import FulfillmentState


CENT = Decimal("0.01")


def _money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


class FulfillmentTools:
    """Deterministic read/write tools for one fulfillment run."""

    def __init__(
        self,
        *,
        dataset: FulfillmentDataset,
        state: FulfillmentState,
        logger: TraceLogger,
    ) -> None:
        self.dataset = dataset
        self.state = state
        self.logger = logger

    # Read-only tools -------------------------------------------------------

    def get_order_context(self, order_id: str) -> tuple[dict[str, Any], str]:
        order = self.dataset.get_order(order_id)
        items = self.dataset.get_order_items(order_id)
        result = {
            "order": order.model_dump(mode="json"),
            "items": [item.model_dump(mode="json") for item in items],
        }
        event_id = self._log_read(
            "get_order_context", {"order_id": order_id}, result
        )
        return result, event_id

    def get_inventory_inputs(self, order_id: str) -> tuple[dict[str, Any], str]:
        items = self.dataset.get_order_items(order_id)
        rows = []
        for item in items:
            inventory = self.state.inventory[item.product_id]
            rows.append(
                {
                    "product_id": item.product_id,
                    "requested_qty": item.quantity,
                    "available_qty": inventory["available_qty"],
                    "reserved_qty": inventory["reserved_qty"],
                    "warehouse_id": inventory["warehouse_id"],
                    "updated_at": inventory["updated_at"],
                }
            )

        result = {"order_id": order_id, "items": rows}
        event_id = self._log_read(
            "get_inventory_inputs", {"order_id": order_id}, result
        )
        return result, event_id

    def get_pricing_inputs(self, order_id: str) -> tuple[dict[str, Any], str]:
        items = self.dataset.get_order_items(order_id)
        result = {
            "order_id": order_id,
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price_usd": item.unit_price_at_purchase_usd,
                }
                for item in items
            ],
        }
        event_id = self._log_read(
            "get_pricing_inputs", {"order_id": order_id}, result
        )
        return result, event_id

    def get_shipping_inputs(self, order_id: str) -> tuple[dict[str, Any], str]:
        order = self.dataset.get_order(order_id)
        items = self.dataset.get_order_items(order_id)
        rate = self.dataset.get_shipping_rate(
            order.shipping_zone,
            order.shipping_service,
        )

        lines = []
        for item in items:
            product = self.dataset.get_product(item.product_id)
            lines.append(
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_weight_kg": product.weight_kg,
                }
            )

        result = {
            "order_id": order_id,
            "zone": order.shipping_zone,
            "service": order.shipping_service,
            "items": lines,
            "rate": rate.model_dump(mode="json"),
        }
        event_id = self._log_read(
            "get_shipping_inputs", {"order_id": order_id}, result
        )
        return result, event_id

    # State-changing tools -------------------------------------------------

    def execute_action(
        self,
        action: ToolAction,
        *,
        triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        before = self.state.snapshot()
        started = time.perf_counter()
        self.logger.log("tool_started", stage=action.tool,
                        data={"arguments": action.model_dump(mode="json"), "mutates_state": True},
                        parent_ids=[triggered_by_artifact_id])
        try:
            return self._execute_action(action, triggered_by_artifact_id=triggered_by_artifact_id)
        except Exception as exc:
            self.logger.log(
                "tool_failed", stage=action.tool,
                data={"tool": action.tool, "arguments": action.model_dump(mode="json"),
                      "error": str(exc), "error_type": type(exc).__name__,
                      "latency_ms": (time.perf_counter() - started) * 1000,
                      "mutates_state": True, "before_state": before,
                      "after_state": self.state.snapshot()},
                parent_ids=[triggered_by_artifact_id],
            )
            raise

    def _execute_action(
        self, action: ToolAction, *, triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        if isinstance(action, ReserveInventoryAction):
            return self.reserve_inventory(
                action,
                triggered_by_artifact_id=triggered_by_artifact_id,
            )
        if isinstance(action, CreateShipmentAction):
            return self.create_shipment(
                action,
                triggered_by_artifact_id=triggered_by_artifact_id,
            )
        if isinstance(action, UpdateOrderStatusAction):
            return self.update_order_status(
                action,
                triggered_by_artifact_id=triggered_by_artifact_id,
            )
        raise TypeError(f"Unsupported executor action: {type(action).__name__}")

    def reserve_inventory(
        self,
        action: ReserveInventoryAction,
        *,
        triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        key = self._idempotency_key(action.tool)
        if key in self.state.idempotency_keys:
            return self._log_duplicate(action.tool, triggered_by_artifact_id)

        before = self.state.snapshot()

        for item in action.items:
            row = self.state.inventory.get(item.product_id)
            if row is None:
                raise ValueError(f"Unknown product in reservation: {item.product_id}")
            if item.quantity > row["available_qty"]:
                raise ValueError(
                    f"Insufficient inventory for {item.product_id}: "
                    f"requested={item.quantity}, available={row['available_qty']}"
                )

        reservation_rows = []
        for item in action.items:
            row = self.state.inventory[item.product_id]
            row["available_qty"] -= item.quantity
            row["reserved_qty"] += item.quantity
            reservation_rows.append(item.model_dump(mode="json"))

        self.state.reservations[self.state.order_id] = reservation_rows
        self.state.idempotency_keys.add(key)
        result = {"status": "reserved", "items": reservation_rows}
        self._log_write(
            action.tool,
            action.model_dump(mode="json"),
            result,
            before,
            triggered_by_artifact_id,
        )
        return result

    def create_shipment(
        self,
        action: CreateShipmentAction,
        *,
        triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        key = self._idempotency_key(action.tool)
        if key in self.state.idempotency_keys:
            return self._log_duplicate(action.tool, triggered_by_artifact_id)

        if self.state.order_id not in self.state.reservations:
            raise ValueError("Cannot create shipment before inventory is reserved.")

        before = self.state.snapshot()
        shipment = {
            "order_id": self.state.order_id,
            "shipping_service": action.shipping_service,
            "shipping_cost_usd": _money(Decimal(str(action.shipping_cost_usd))),
            "total_weight_kg": action.total_weight_kg,
            "status": "scheduled",
        }
        self.state.shipments[self.state.order_id] = shipment
        self.state.idempotency_keys.add(key)
        result = deepcopy(shipment)
        self._log_write(
            action.tool,
            action.model_dump(mode="json"),
            result,
            before,
            triggered_by_artifact_id,
        )
        return result

    def update_order_status(
        self,
        action: UpdateOrderStatusAction,
        *,
        triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        key = self._idempotency_key(action.tool)
        if key in self.state.idempotency_keys:
            return self._log_duplicate(action.tool, triggered_by_artifact_id)

        before = self.state.snapshot()
        self.state.order_status = action.status
        self.state.idempotency_keys.add(key)
        result = {"order_id": self.state.order_id, "status": action.status}
        self._log_write(
            action.tool,
            action.model_dump(mode="json"),
            result,
            before,
            triggered_by_artifact_id,
        )
        return result

    # Logging helpers ------------------------------------------------------

    def _idempotency_key(self, tool_name: str) -> str:
        return f"{self.logger.run_id}:{self.state.order_id}:{tool_name}"

    def _log_read(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        return self.logger.log(
            "tool_completed",
            stage=tool_name,
            data={
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
                "mutates_state": False,
            },
        )

    def _log_write(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        before: dict[str, Any],
        triggered_by_artifact_id: str,
    ) -> None:
        self.logger.log(
            "tool_completed",
            stage=tool_name,
            data={
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
                "mutates_state": True,
                "before_state": before,
                "after_state": self.state.snapshot(),
                "triggered_by_artifact_id": triggered_by_artifact_id,
            },
            parent_ids=[triggered_by_artifact_id],
        )

    def _log_duplicate(
        self,
        tool_name: str,
        triggered_by_artifact_id: str,
    ) -> dict[str, Any]:
        result = {"status": "duplicate_ignored", "tool": tool_name}
        self.logger.log(
            "tool_duplicate_ignored",
            stage=tool_name,
            data={
                "tool": tool_name,
                "result": result,
                "triggered_by_artifact_id": triggered_by_artifact_id,
            },
            parent_ids=[triggered_by_artifact_id],
        )
        return result
