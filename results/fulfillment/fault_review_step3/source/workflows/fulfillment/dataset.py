from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from data.loader import DEFAULT_DATASET_PATH, load_dataset

from .models import (
    FulfillmentGroundTruth,
    InventoryRecord,
    OrderItemRecord,
    OrderRecord,
    ProductRecord,
    ShippingRateRecord,
)


class FulfillmentDataset:
    """Typed access to the fulfillment-related sections of dataset.json."""

    REQUIRED_SECTIONS = {
        "products",
        "inventory",
        "shipping_rates",
        "orders",
        "order_items",
        "fulfillment_ground_truth",
    }

    def __init__(self, path: str | Path = DEFAULT_DATASET_PATH) -> None:
        raw = load_dataset(path)
        missing = self.REQUIRED_SECTIONS - raw.keys()
        if missing:
            raise ValueError(
                f"Dataset is missing required sections: {sorted(missing)}"
            )

        self.products = {
            row.product_id: row
            for row in (
                ProductRecord.model_validate(item)
                for item in raw["products"]
            )
        }
        self.inventory = {
            row.product_id: row
            for row in (
                InventoryRecord.model_validate(item)
                for item in raw["inventory"]
            )
        }
        self.shipping_rates = {
            (row.zone, row.service): row
            for row in (
                ShippingRateRecord.model_validate(item)
                for item in raw["shipping_rates"]
            )
        }
        self.orders = {
            row.order_id: row
            for row in (
                OrderRecord.model_validate(item)
                for item in raw["orders"]
            )
        }

        order_items: dict[str, list[OrderItemRecord]] = defaultdict(list)
        for item in raw["order_items"]:
            row = OrderItemRecord.model_validate(item)
            order_items[row.order_id].append(row)
        self.order_items = dict(order_items)

        self.ground_truth = {
            row.order_id: row
            for row in (
                FulfillmentGroundTruth.model_validate(item)
                for item in raw["fulfillment_ground_truth"]
            )
        }

        self._validate_references()

    def list_order_ids(self) -> list[str]:
        return sorted(self.orders)

    def get_order(self, order_id: str) -> OrderRecord:
        try:
            return self.orders[order_id]
        except KeyError as exc:
            raise KeyError(f"Unknown order_id: {order_id}") from exc

    def get_order_items(self, order_id: str) -> list[OrderItemRecord]:
        self.get_order(order_id)
        return list(self.order_items.get(order_id, []))

    def get_product(self, product_id: str) -> ProductRecord:
        try:
            return self.products[product_id]
        except KeyError as exc:
            raise KeyError(f"Unknown product_id: {product_id}") from exc

    def get_inventory(self, product_id: str) -> InventoryRecord:
        try:
            return self.inventory[product_id]
        except KeyError as exc:
            raise KeyError(f"No inventory row for product_id: {product_id}") from exc

    def get_shipping_rate(
        self,
        zone: str,
        service: str,
    ) -> ShippingRateRecord:
        try:
            return self.shipping_rates[(zone, service)]
        except KeyError as exc:
            raise KeyError(
                f"No shipping rate for zone={zone!r}, service={service!r}"
            ) from exc

    def get_ground_truth(self, order_id: str) -> FulfillmentGroundTruth:
        try:
            return self.ground_truth[order_id]
        except KeyError as exc:
            raise KeyError(f"No ground truth for order_id: {order_id}") from exc

    def _validate_references(self) -> None:
        for order_id, items in self.order_items.items():
            if order_id not in self.orders:
                raise ValueError(f"Order item references unknown order: {order_id}")
            for item in items:
                if item.product_id not in self.products:
                    raise ValueError(
                        f"Order item references unknown product: {item.product_id}"
                    )
                if item.product_id not in self.inventory:
                    raise ValueError(
                        f"No inventory for ordered product: {item.product_id}"
                    )

        for order in self.orders.values():
            if order.order_id not in self.order_items:
                raise ValueError(f"Order has no line items: {order.order_id}")
            if (
                order.shipping_zone,
                order.shipping_service,
            ) not in self.shipping_rates:
                raise ValueError(
                    f"Order {order.order_id} references an unknown shipping rate."
                )
            if order.order_id not in self.ground_truth:
                raise ValueError(
                    f"Order {order.order_id} has no fulfillment ground truth."
                )
