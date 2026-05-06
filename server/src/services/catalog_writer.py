"""Catalog writer — the only legal path for product mutations.

Sync invariant: DynamoDB `products` is the source of truth; OpenSearch
`product-catalog` is a derived index. Every mutation must go through
this writer so both stores stay in lockstep.

Carve-out: review-aggregate updates (rating, reviewCount) are exempt
because neither field appears in the embed text or vector metadata. They
flow through CatalogSnapshot.bump_review_aggregates and only touch
Dynamo + the snapshot.
"""

from __future__ import annotations

import logging

from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_PRODUCTS
from shared.dynamo import DynamoClient
from shared.vector_store import VectorStoreProtocol

from ..schemas.catalog import Product
from .catalog_snapshot import CatalogSnapshot

log = logging.getLogger(__name__)


def _build_embed_text(product: Product) -> str:
    """Concatenate the product's text-bearing fields into one passage so
    the embedding represents what a shopper actually searches for."""
    parts: list[str] = [product.name, product.brand, product.description]
    if product.tags:
        parts.append(" ".join(product.tags))
    if product.features:
        parts.append(" ".join(product.features))
    if product.specification:
        parts.append(" ".join(product.specification))
    return " ".join(p for p in parts if p)


def _build_vector_metadata(product: Product) -> dict:
    """Filterable fields stored alongside the vector for hybrid queries.
    Mirrors the field list defined in the product-catalog index mapping."""
    return {
        "slug": product.slug,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "vertical": product.vertical or "general",
        "price": float(product.price),
        "freeDelivery": bool(product.free_delivery),
        "tags": product.tags or [],
    }


class CatalogWriter:
    def __init__(
        self,
        dynamo: DynamoClient,
        bedrock: BedrockClientProtocol,
        vectors: VectorStoreProtocol,
        snapshot: CatalogSnapshot,
    ) -> None:
        self._dynamo = dynamo
        self._bedrock = bedrock
        self._vectors = vectors
        self._snapshot = snapshot

    def upsert_product(self, product: Product) -> None:
        embed_text = _build_embed_text(product)
        vector = self._bedrock.embed(embed_text)

        # Dynamo first (source of truth). If embedding failed we'd never
        # reach here. If the OpenSearch upsert below fails, the reconcile
        # script picks up the drift.
        self._dynamo.put_product(product.model_dump(by_alias=True, exclude_none=True))

        # AOSS quirk: VECTORSEARCH collections reject client-supplied `_id`,
        # so each `index()` call creates a brand-new doc with an auto id —
        # turning every re-seed into a duplicate-doubler. Delete any existing
        # slug-matched docs FIRST so the upsert is truly idempotent on AOSS.
        # Local OpenSearch ignores this (it overwrites by client-supplied id).
        client = getattr(self._vectors, "client", None)
        if client is not None and getattr(self._vectors, "is_aoss", False):
            try:
                client.delete_by_query(
                    index=COLLECTION_PRODUCTS,
                    body={"query": {"term": {"slug": product.slug}}},
                    conflicts="proceed",
                    refresh=False,
                )
            except Exception:
                # Non-fatal: missing pre-existing docs is fine, query errors
                # are logged but don't block the new insert below. Reconcile
                # cleans up any drift.
                log.exception("AOSS pre-delete by slug=%s failed", product.slug)

        try:
            self._vectors.upsert(
                COLLECTION_PRODUCTS,
                doc_id=product.slug,
                vector=vector,
                metadata=_build_vector_metadata(product),
            )
        except Exception:
            log.exception(
                "vector upsert failed for slug=%s — Dynamo updated, vectors stale; "
                "run reconcile-products to repair",
                product.slug,
            )
            raise

        self._snapshot.upsert_in_snapshot(product)

    def delete_product(self, slug: str) -> None:
        self._dynamo.delete_product(slug)
        try:
            # OpenSearch delete-by-id; falls through to no-op for InMemory
            # store (it has no matching helper, and InMemory is dev-only).
            client = getattr(self._vectors, "client", None)
            if client is not None:
                client.delete(index=COLLECTION_PRODUCTS, id=slug, ignore=[404])
        except Exception:
            log.exception("vector delete failed for slug=%s", slug)
            raise
        self._snapshot.delete_in_snapshot(slug)
