"""Checkout service.

Sequence per POST /checkout:
  1. Validate every item against the catalog snapshot (product exists,
     quantity > 0).
  2. Recompute line totals + order subtotal from the catalog (anti-tamper —
     the client-supplied `subtotal` is ignored).
  3. Pull the customer's default address from the profile so the order
     row carries `destinationLabel` + `deliveryAddressId`.
  4. Write the order row via DynamoClient.orders_put.
  5. Clear the customer's cart so the next /me/cart returns empty.
  6. Return {orderId, status, placedAt} matching the frontend contract.

Does NOT emit any events — the events pipeline is out of scope for this
milestone and the existing POST /events handler is unchanged.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from shared.dynamo import DynamoClient
from shared.schemas import new_uuid, utc_now_iso

from ..schemas.orders import CheckoutInput, CheckoutResponse, OrderLine
from ..services.catalog_snapshot import CatalogSnapshot

log = logging.getLogger(__name__)


class CheckoutService:
    def __init__(self, dynamo: DynamoClient, snapshot: CatalogSnapshot) -> None:
        self._dynamo = dynamo
        self._snapshot = snapshot

    def checkout(self, customer_id: str, body: CheckoutInput) -> CheckoutResponse:
        if not body.items:
            raise HTTPException(status_code=400, detail="cart is empty")

        # 1 + 2: resolve every line against the catalog snapshot. Server
        # decides the unit price; client-supplied subtotal is ignored.
        lines: list[OrderLine] = []
        total = 0.0
        for item in body.items:
            product = self._product_for(item.product_id)
            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown product: {item.product_id}",
                )
            unit_price = float(product.price)
            line_total = unit_price * item.quantity
            total += line_total
            lines.append(
                OrderLine(
                    productId=product.id,
                    slug=product.slug,
                    name=product.name,
                    quantity=item.quantity,
                    unitPrice=unit_price,
                )
            )
        total = round(total, 2)

        # 3: best-guess destination from the profile (or fall back to
        # the body's address fields if no profile/default exists).
        destination_label, delivery_address_id = self._resolve_destination(customer_id, body)

        # 4: persist the order.
        order_id = f"ord-{new_uuid()[:8]}"
        placed_at = utc_now_iso()
        order = {
            "id": order_id,
            "status": "placed",
            "placedAt": placed_at,
            "total": total,
            "currency": "INR",
            "destinationLabel": destination_label,
            "lineCount": sum(l.quantity for l in lines),
            "deliveryAddressId": delivery_address_id,
            "lines": [l.model_dump(by_alias=True, exclude_none=True) for l in lines],
        }
        self._dynamo.orders_put(customer_id, order)

        # 5: clear the cart.
        cleared = self._dynamo.cart_clear(customer_id)
        log.info(
            "checkout completed: customer=%s order=%s total=%s cart_lines_cleared=%d",
            customer_id, order_id, total, cleared,
        )

        # 6: response matches the frontend contract (CheckoutResponse).
        return CheckoutResponse(orderId=order_id, status="confirmed", placedAt=placed_at)

    # --- internals ------------------------------------------------------

    def _product_for(self, product_id: str):
        for p in self._snapshot.list_products():
            if p.id == product_id or p.slug == product_id:
                return p
        return None

    def _resolve_destination(self, customer_id: str, body: CheckoutInput) -> tuple[str, str | None]:
        """Pick an address: customer's default profile address if any,
        else fall back to a synthetic label built from the body."""
        profile = self._dynamo.profile_get(customer_id)
        if profile:
            addresses = profile.get("addresses") or []
            default = next((a for a in addresses if a.get("isDefault")), None)
            if not default and addresses:
                default = addresses[0]
            if default:
                label = f"{default.get('label', 'Shipping')} · {default.get('city', '')}".strip(" ·")
                return label, default.get("id")
        return f"{body.full_name} · {body.city}", None
