"""Pydantic models for order history + checkout.

Mirrors apps/web/src/shared/api/contracts.ts:217-245, 308-323.

CheckoutInput / CheckoutResponse are defined here for M3 to consume; the
M2 commit only ships GET /me/orders.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OrderStatus = Literal["placed", "processing", "shipped", "delivered", "cancelled"]
PaymentMethod = Literal["card", "wallet"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class OrderLine(_CamelModel):
    product_id: str = Field(alias="productId")
    slug: str
    name: str
    quantity: int
    unit_price: float = Field(alias="unitPrice")
    selected_options: dict[str, str] | None = Field(default=None, alias="selectedOptions")


class OrderSummary(_CamelModel):
    id: str
    status: OrderStatus
    placed_at: str = Field(alias="placedAt")
    total: float
    currency: str
    destination_label: str = Field(alias="destinationLabel")
    line_count: int = Field(alias="lineCount")
    tracking_url: str | None = Field(default=None, alias="trackingUrl")
    lines: list[OrderLine] | None = None
    delivery_address_id: str | None = Field(default=None, alias="deliveryAddressId")


class OrderListResponse(_CamelModel):
    items: list[OrderSummary]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int


class CheckoutItemInput(_CamelModel):
    product_id: str = Field(alias="productId")
    quantity: int = Field(gt=0)


class CheckoutInput(_CamelModel):
    email: str
    full_name: str = Field(alias="fullName")
    address: str
    city: str
    country: str
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    subtotal: float
    items: list[CheckoutItemInput]


class CheckoutResponse(_CamelModel):
    order_id: str = Field(alias="orderId")
    status: Literal["confirmed"]
    placed_at: str = Field(alias="placedAt")
