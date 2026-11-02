from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
import time
import json

from core.budget import RunBudget
from .faults import FaultInjector

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
        injector: FaultInjector | None = None,
        budget: RunBudget | None = None,
    ) -> None:
        self.dataset = dataset
        self.state = state
        self.logger = logger
        self.injector = injector or FaultInjector(None)
        self.budget = budget or RunBudget()
        self.last_write_event_id: str | None = None
        self.action_started = 0.0
        self.action_call_id: str | None = None
        self.action_audit_id: str | None = None

    # Read-only tools -------------------------------------------------------

    def get_order_context(self, order_id: str) -> tuple[dict[str, Any], str]:
        order = self.dataset.get_order(order_id)
        items = self.dataset.get_order_items(order_id)
        result = {
            "order": order.model_dump(mode="json"),
            "items": [item.model_dump(mode="json") for item in items],
        }
        return self._log_read(
            "get_order_context", {"order_id": order_id}, result
        )

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
        return self._log_read(
            "get_inventory_inputs", {"order_id": order_id}, result
        )

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
        return self._log_read(
            "get_pricing_inputs", {"order_id": order_id}, result
        )

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
        return self._log_read(
            "get_shipping_inputs", {"order_id": order_id}, result
        )

    # State-changing tools -------------------------------------------------

    def execute_action(
        self,
        action: ToolAction,
        *,
        triggered_by_artifact_id: str,
        audit_event_id: str | None = None,
    ) -> dict[str, Any]:
        before = self.state.snapshot()
        started = time.perf_counter()
        self.action_started = started
        self.action_audit_id = audit_event_id
        self.budget.tool()
        start_id = self.logger.log("tool_started", stage=action.tool,
                        data={"arguments": action.model_dump(mode="json"), "mutates_state": True,
                              "audit_event_id": audit_event_id},
                        parent_ids=[triggered_by_artifact_id] + ([audit_event_id] if audit_event_id else []))
        self.action_call_id = start_id
        was_applied = self.injector.applied
        try:
            self.injector.apply(action.model_dump(mode='json'), stage=action.tool,
                                surface='tool_call', logger=self.logger, parent_id=start_id)
            return self._execute_action(action, triggered_by_artifact_id=triggered_by_artifact_id)
        except Exception as exc:
            self.logger.log(
                "tool_failed", stage=action.tool,
                data={"tool": action.tool, "arguments": action.model_dump(mode="json"),
                      "error": str(exc), "error_type": type(exc).__name__,
                      "tool_call_id": start_id, "audit_event_id": audit_event_id,
                      "latency_ms": (time.perf_counter() - started) * 1000,
                      "mutates_state": True, "before_state": before,
                      "after_state": self.state.snapshot()},
                parent_ids=[triggered_by_artifact_id, start_id] +
                           ([audit_event_id] if audit_event_id else []) +
                           ([self.injector.event_id] if not was_applied and self.injector.applied else []),
            )
            raise
        finally:
            self.action_call_id = self.action_audit_id = None
            self.action_started = 0.0

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

        if len({item.product_id for item in action.items}) != len(action.items):
            raise ValueError('Duplicate products in one reservation are not allowed.')
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
    ) -> tuple[dict[str, Any], str]:
        self.budget.tool()
        started = time.perf_counter()
        start_id = self.logger.log('tool_started', stage=tool_name,
                                   data={'tool': tool_name, 'arguments': arguments, 'mutates_state': False})
        stage = {'get_inventory_inputs': 'inventory_agent', 'get_pricing_inputs': 'pricing_agent',
                 'get_shipping_inputs': 'shipping_agent'}.get(tool_name, tool_name)
        was_applied = self.injector.applied
        try:
            result = self.injector.apply(result, stage=stage, surface='tool_response',
                                         logger=self.logger, parent_id=start_id)
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict):
                raise ValueError('Tool response must be a JSON object')
        except Exception as exc:
            self.logger.log('tool_failed', stage=tool_name,
                            data={'tool': tool_name, 'arguments': arguments, 'error': str(exc),
                                  'tool_call_id': start_id,
                                  'error_type': type(exc).__name__, 'mutates_state': False,
                                  'latency_ms': (time.perf_counter() - started) * 1000},
                            parent_ids=[start_id] + ([self.injector.event_id] if not was_applied and self.injector.applied else []))
            raise
        event_id = self.logger.log(
            "tool_completed",
            stage=tool_name,
            data={
                "tool": tool_name,
                "tool_call_id": start_id,
                "arguments": arguments,
                "result": result,
                "mutates_state": False,
                "latency_ms": (time.perf_counter() - started) * 1000,
            },
            parent_ids=[start_id] + ([self.injector.event_id] if not was_applied and self.injector.applied else []),
        )
        return result, event_id

    def _log_write(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        before: dict[str, Any],
        triggered_by_artifact_id: str,
    ) -> None:
        event_id = self.logger.log(
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
                "tool_call_id": self.action_call_id, "audit_event_id": self.action_audit_id,
                "latency_ms": ((time.perf_counter() - self.action_started) * 1000
                               if self.action_started else None),
            },
            parent_ids=[triggered_by_artifact_id] + [value for value in
                        (self.action_call_id, self.action_audit_id, self.last_write_event_id) if value],
        )
        self.last_write_event_id = event_id

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
                "tool_call_id": self.action_call_id, "audit_event_id": self.action_audit_id,
                "mutates_state": False,
                "latency_ms": ((time.perf_counter() - self.action_started) * 1000
                               if self.action_started else None),
            },
            parent_ids=[triggered_by_artifact_id] + [value for value in
                        (self.action_call_id, self.action_audit_id) if value],
        )
        return result
