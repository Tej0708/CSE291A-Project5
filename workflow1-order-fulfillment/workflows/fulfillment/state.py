from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .dataset import FulfillmentDataset


@dataclass
class FulfillmentState:
    """Mutable state for one isolated fulfillment run."""

    order_id: str
    inventory: dict[str, dict[str, Any]]
    order_status: str
    reservations: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    shipments: dict[str, dict[str, Any]] = field(default_factory=dict)
    idempotency_keys: set[str] = field(default_factory=set)

    @classmethod
    def from_dataset(
        cls,
        dataset: FulfillmentDataset,
        order_id: str,
    ) -> "FulfillmentState":
        order = dataset.get_order(order_id)

        inventory = {
            product_id: record.model_dump(mode="json")
            for product_id, record in dataset.inventory.items()
        }

        return cls(
            order_id=order_id,
            inventory=deepcopy(inventory),
            order_status=order.order_status,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "order_status": self.order_status,
            "inventory": deepcopy(self.inventory),
            "reservations": deepcopy(self.reservations),
            "shipments": deepcopy(self.shipments),
            "idempotency_keys": sorted(self.idempotency_keys),
        }
