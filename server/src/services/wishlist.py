"""Wishlist service — get / add / delete.

Same enrichment pattern as cart: rows carry only `product_id` and
`added_at`; display fields are resolved from the catalog snapshot at
read time.
"""

from __future__ import annotations

from fastapi import HTTPException

from shared.dynamo import DynamoClient
from shared.schemas import utc_now_iso

from ..schemas.cart import (
    AddWishlistItemBody,
    WishlistItem,
    WishlistResponse,
)
from .catalog_snapshot import CatalogSnapshot


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


class WishlistService:
    def __init__(self, dynamo: DynamoClient, snapshot: CatalogSnapshot) -> None:
        self._dynamo = dynamo
        self._snapshot = snapshot

    def get_wishlist(self, customer_id: str) -> WishlistResponse:
        rows = self._dynamo.wishlist_get(customer_id)
        items: list[WishlistItem] = []
        for row in rows:
            row = _strip_dynamo_keys(row)
            product = self._product_for(row.get("product_id"))
            if not product:
                continue
            items.append(
                WishlistItem(
                    productId=product.id,
                    slug=product.slug,
                    name=product.name,
                    image=product.image,
                    unitPrice=float(product.price),
                    addedAt=row.get("added_at") or row.get("addedAt") or utc_now_iso(),
                )
            )
        return WishlistResponse(items=items)

    def add_item(self, customer_id: str, body: AddWishlistItemBody) -> WishlistResponse:
        product = self._product_for(body.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        # Re-adding is idempotent — we keep the original addedAt.
        existing = self._dynamo.wishlist_get_item(customer_id, body.product_id)
        added_at = (
            existing.get("added_at") or existing.get("addedAt")
            if existing
            else utc_now_iso()
        )
        self._dynamo.wishlist_put_item(customer_id, {
            "product_id": body.product_id,
            "added_at": added_at,
        })
        return self.get_wishlist(customer_id)

    def delete_item(self, customer_id: str, product_id: str) -> WishlistResponse:
        deleted = self._dynamo.wishlist_delete_item(customer_id, product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="wishlist item not found")
        return self.get_wishlist(customer_id)

    def _product_for(self, product_id: str | None):
        if not product_id:
            return None
        for p in self._snapshot.list_products():
            if p.id == product_id or p.slug == product_id:
                return p
        return None
