"""In-memory catalog snapshot.

DynamoDB `products` and `categories` are the source of truth; this snapshot
is loaded once at server startup and kept in sync with write-through
mutations through CatalogWriter. Reads (list, get_product, list_categories)
serve from memory so the catalog endpoints don't pay a Dynamo round-trip.

Single-replica safe. Multi-replica deployment would need a Redis pub/sub
invalidation channel (out of scope here).
"""

from __future__ import annotations

import logging
import threading

from shared.dynamo import DynamoClient

from ..schemas.catalog import Category, Product

log = logging.getLogger(__name__)


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


class CatalogSnapshot:
    def __init__(self, dynamo: DynamoClient) -> None:
        self._dynamo = dynamo
        self._lock = threading.RLock()
        self._products_by_slug: dict[str, Product] = {}
        self._categories: list[Category] = []

    def refresh(self) -> None:
        """Reload everything from Dynamo. Called at startup and on demand."""
        with self._lock:
            raw_products = self._dynamo.scan_products()
            products = [Product.model_validate(_strip_dynamo_keys(row)) for row in raw_products]
            self._products_by_slug = {p.slug: p for p in products}

            raw_categories = self._dynamo.list_categories()
            self._categories = [
                Category.model_validate(_strip_dynamo_keys(row)) for row in raw_categories
            ]
            log.info(
                "catalog snapshot loaded: %d products, %d categories",
                len(self._products_by_slug),
                len(self._categories),
            )

    def list_products(self) -> list[Product]:
        with self._lock:
            return list(self._products_by_slug.values())

    def get_product(self, slug: str) -> Product | None:
        with self._lock:
            return self._products_by_slug.get(slug)

    def list_categories(self) -> list[Category]:
        with self._lock:
            return list(self._categories)

    # --- mutators (called by CatalogWriter) ----------------------------

    def upsert_in_snapshot(self, product: Product) -> None:
        with self._lock:
            self._products_by_slug[product.slug] = product

    def delete_in_snapshot(self, slug: str) -> None:
        with self._lock:
            self._products_by_slug.pop(slug, None)

    def bump_review_aggregates(self, slug: str, rating: float, review_count: int) -> None:
        """Update Dynamo + snapshot. Vector unchanged because rating and
        reviewCount are NOT part of the embed text or vector metadata —
        documented carve-out from the catalog↔vector sync invariant."""
        self._dynamo.update_product_review_aggregates(slug, rating, review_count)
        with self._lock:
            existing = self._products_by_slug.get(slug)
            if existing:
                updated = existing.model_copy(update={"rating": rating, "review_count": review_count})
                self._products_by_slug[slug] = updated
