"""Cart service — get / add / patch / delete / clear.

Lines stored in DynamoDB carry only the canonical fields (productId,
quantity, selectedOptions, addedAt). Display fields (slug, name, image,
unitPrice) are looked up from the in-memory CatalogSnapshot at read
time so the response is fully renderable without a second round-trip,
and price changes in the catalog flow through naturally.
"""

from __future__ import annotations

from fastapi import HTTPException

from shared.dynamo import DynamoClient
from shared.schemas import utc_now_iso

from ..schemas.cart import (
    AddCartItemBody,
    CartItem,
    CartResponse,
    PatchCartItemBody,
)
from .catalog_snapshot import CatalogSnapshot


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


class CartService:
    def __init__(self, dynamo: DynamoClient, snapshot: CatalogSnapshot) -> None:
        self._dynamo = dynamo
        self._snapshot = snapshot

    # --- read -----------------------------------------------------------

    def get_cart(self, customer_id: str) -> CartResponse:
        rows = self._dynamo.cart_get(customer_id)
        items: list[CartItem] = []
        subtotal = 0.0
        last_updated: str | None = None

        for row in rows:
            row = _strip_dynamo_keys(row)
            product_id = row.get("product_id")
            product = self._product_for(product_id)
            if not product:
                # Product was removed from the catalog after being added
                # to the cart. Skip silently — line is effectively dead.
                continue
            quantity = int(row.get("quantity", 1))
            unit_price = float(product.price)
            subtotal += quantity * unit_price
            added_at = row.get("added_at") or row.get("addedAt") or utc_now_iso()
            if last_updated is None or added_at > last_updated:
                last_updated = added_at

            items.append(
                CartItem(
                    productId=product.id,
                    slug=product.slug,
                    name=product.name,
                    image=product.image,
                    unitPrice=unit_price,
                    quantity=quantity,
                    selectedOptions=row.get("selected_options") or row.get("selectedOptions"),
                    addedAt=added_at,
                )
            )

        return CartResponse(
            items=items,
            itemCount=sum(i.quantity for i in items),
            subtotal=round(subtotal, 2),
            updatedAt=last_updated,
        )

    # --- mutations ------------------------------------------------------

    def add_item(self, customer_id: str, body: AddCartItemBody) -> CartResponse:
        product = self._product_for(body.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")

        existing = self._dynamo.cart_get_item(customer_id, body.product_id)
        if existing:
            # Adding the same product again bumps quantity (most common
            # storefront behavior). selectedOptions overwritten if supplied.
            new_quantity = int(existing.get("quantity", 0)) + body.quantity
            self._dynamo.cart_put_item(customer_id, {
                "product_id": body.product_id,
                "quantity": new_quantity,
                "selected_options": body.selected_options or existing.get("selected_options") or existing.get("selectedOptions"),
                "added_at": existing.get("added_at") or existing.get("addedAt") or utc_now_iso(),
            })
        else:
            self._dynamo.cart_put_item(customer_id, {
                "product_id": body.product_id,
                "quantity": body.quantity,
                "selected_options": body.selected_options,
                "added_at": utc_now_iso(),
            })
        return self.get_cart(customer_id)

    def patch_item(
        self,
        customer_id: str,
        product_id: str,
        body: PatchCartItemBody,
    ) -> CartResponse:
        existing = self._dynamo.cart_get_item(customer_id, product_id)
        if not existing:
            raise HTTPException(status_code=404, detail="cart item not found")

        merged = {
            "product_id": product_id,
            "quantity": body.quantity if body.quantity is not None else int(existing.get("quantity", 1)),
            "selected_options": (
                body.selected_options
                if body.selected_options is not None
                else existing.get("selected_options") or existing.get("selectedOptions")
            ),
            "added_at": existing.get("added_at") or existing.get("addedAt") or utc_now_iso(),
        }
        self._dynamo.cart_put_item(customer_id, merged)
        return self.get_cart(customer_id)

    def delete_item(self, customer_id: str, product_id: str) -> CartResponse:
        deleted = self._dynamo.cart_delete_item(customer_id, product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="cart item not found")
        return self.get_cart(customer_id)

    def clear(self, customer_id: str) -> int:
        return self._dynamo.cart_clear(customer_id)

    # --- internals ------------------------------------------------------

    def _product_for(self, product_id: str | None):
        if not product_id:
            return None
        # Cart product_id uses the canonical product `id` field, but the
        # snapshot keys by slug. Walk products to resolve.
        for p in self._snapshot.list_products():
            if p.id == product_id or p.slug == product_id:
                return p
        return None
