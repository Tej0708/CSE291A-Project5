from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


# Dataset records -----------------------------------------------------------


class ProductRecord(BaseModel):
    product_id: str
    product_name: str
    unit_price_usd: float
    weight_kg: float
    active: bool


class InventoryRecord(BaseModel):
    product_id: str
    warehouse_id: str
    available_qty: int
    reserved_qty: int
    updated_at: str


class ShippingRateRecord(BaseModel):
    zone: str
    service: str
    base_price_usd: float
    price_per_kg_usd: float
    max_weight_kg: float
    estimated_days: int


class OrderRecord(BaseModel):
    order_id: str
    customer_id: str
    order_date: str
    shipping_zone: str
    shipping_service: str
    payment_status: str
    order_status: str


class OrderItemRecord(BaseModel):
    order_item_id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price_at_purchase_usd: float


class FulfillmentGroundTruth(BaseModel):
    order_id: str
    expected_decision: Literal[
        "approve_fulfillment",
        "reject_insufficient_stock",
        "reject_shipping_constraint",
    ]
    expected_subtotal_usd: float
    expected_shipping_usd: float | None = None
    expected_total_usd: float | None = None
    ground_truth_reason: str

    @field_validator("expected_shipping_usd", "expected_total_usd", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        return None if value == "" else value


# Agent outputs -------------------------------------------------------------


class InventoryLineResult(BaseModel):
    product_id: str
    requested_qty: int = Field(ge=1)
    available_qty: int = Field(ge=0)
    sufficient: bool


class InventoryResult(BaseModel):
    items: list[InventoryLineResult]
    all_items_available: bool


class PricingLineResult(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    unit_price_usd: float = Field(ge=0)
    line_total_usd: float = Field(ge=0)


class PricingResult(BaseModel):
    items: list[PricingLineResult]
    subtotal_usd: float = Field(ge=0)


class ShippingResult(BaseModel):
    zone: str
    service: str
    total_weight_kg: float = Field(ge=0)
    shipping_cost_usd: float = Field(ge=0)
    max_weight_kg: float = Field(gt=0)
    within_weight_limit: bool
    estimated_days: int = Field(ge=0)


class FulfillmentPlan(BaseModel):
    order_id: str
    decision: Literal[
        "approve_fulfillment",
        "reject_insufficient_stock",
        "reject_shipping_constraint",
    ]
    reason: str
    subtotal_usd: float = Field(ge=0)
    shipping_service: str | None = None
    total_weight_kg: float | None = Field(default=None, ge=0)
    shipping_usd: float | None = Field(default=None, ge=0)
    total_usd: float | None = Field(default=None, ge=0)


# Executor actions ----------------------------------------------------------


class ReservationItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)


class ReserveInventoryAction(BaseModel):
    tool: Literal["reserve_inventory"]
    items: list[ReservationItem]


class CreateShipmentAction(BaseModel):
    tool: Literal["create_shipment"]
    shipping_service: str
    shipping_cost_usd: float = Field(ge=0)
    total_weight_kg: float = Field(ge=0)


class UpdateOrderStatusAction(BaseModel):
    tool: Literal["update_order_status"]
    status: Literal["fulfilled", "rejected_insufficient_stock", "rejected_shipping_constraint"]


ToolAction = Annotated[
    ReserveInventoryAction | CreateShipmentAction | UpdateOrderStatusAction,
    Field(discriminator="tool"),
]


class ExecutionDecision(BaseModel):
    actions: list[ToolAction]
