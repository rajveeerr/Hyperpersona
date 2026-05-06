"""Hybrid product search — text filter + vector similarity.

When `q` is present we embed the query, KNN against the product-catalog
collection, and union the result with substring matches so exact-name
hits are never lost. The combined set is then run through the structural
filter engine (vertical / freeDelivery / price / tags / category) and
sort/page applied.

When `q` is absent the route falls back to plain catalog filtering.
"""

from __future__ import annotations

import logging
from typing import Iterable

from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_PRODUCTS
from shared.vector_store import VectorStoreProtocol

from ..schemas.catalog import Product, ProductListResponse, SortOrder
from .catalog_filter import (
    FilterParams,
    apply_product_filters,
    filter_products_response,
)

log = logging.getLogger(__name__)

# k for the KNN call; we want to over-fetch so structural filters still
# leave a usable slice. The catalog is small (~30 SKUs) so a high k is
# essentially free.
_KNN_K = 48


def _substring_matches(products: Iterable[Product], q: str) -> list[Product]:
    """Mirrors the q-handling in apply_product_filters: substring match
    across name / brand / description / tags / features."""
    needle = q.lower()
    out: list[Product] = []
    for p in products:
        haystack = [
            p.name,
            p.brand,
            p.description,
            *(p.tags or []),
            *p.features,
        ]
        if any(needle in (field or "").lower() for field in haystack):
            out.append(p)
    return out


def hybrid_search(
    all_products: list[Product],
    params: FilterParams,
    sort: SortOrder,
    page: int,
    page_size: int,
    personalized: bool,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
) -> ProductListResponse:
    q = params.q
    if not q:
        # No query → pure structural filtering.
        return filter_products_response(
            all_products, params, sort=sort, page=page, page_size=page_size, personalized=personalized,
        )

    # Build a quick by-slug lookup from the snapshot's products so we can
    # resolve KNN hits to full Product objects.
    by_slug = {p.slug: p for p in all_products}

    knn_slugs: list[str] = []
    try:
        embedding = bedrock.embed(q)
        knn_hits = vectors.search(COLLECTION_PRODUCTS, query=embedding, k=_KNN_K)
        # OpenSearchClient flattens metadata; "slug" is on the result.
        # InMemory store also flattens metadata into the dict via **md.
        knn_slugs = [hit.get("slug") or hit.get("id") for hit in knn_hits if hit]
    except Exception:
        log.exception("vector search failed for q=%r — falling back to text-only", q)

    knn_products = [by_slug[s] for s in knn_slugs if s in by_slug]
    text_products = _substring_matches(all_products, q)

    # Union, preserving KNN order first (they're scored), then any
    # text-only matches the KNN missed.
    seen: set[str] = set()
    combined: list[Product] = []
    for p in knn_products + text_products:
        if p.slug in seen:
            continue
        seen.add(p.slug)
        combined.append(p)

    # Apply remaining structural filters on the combined set. We pass an
    # explicit FilterParams without `q` so apply_product_filters doesn't
    # re-run substring matching (we've already done that union above).
    structural_only = FilterParams(
        category=params.category,
        brand=params.brand,
        vertical=params.vertical,
        free_delivery=params.free_delivery,
        tags=params.tags,
        min_price=params.min_price,
        max_price=params.max_price,
    )
    return filter_products_response(
        combined,
        structural_only,
        sort=sort,
        page=page,
        page_size=page_size,
        personalized=personalized,
    )
