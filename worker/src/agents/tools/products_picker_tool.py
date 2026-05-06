"""Pick personalized in-stock products via blended-KNN over product-catalog.

Reuses the same blended-vector pattern as the complement pipeline:

    query_vec = (1 - α) · context_vec + α · preference_vec

where preference_vec is built from ACE-ranked customer facts (polarity-aware,
positive facts pull toward, polarity=-1 facts push away). KNN over OpenSearch
`product-catalog`, hydrate from storefront `products`, drop out-of-stock,
cap at limit. Returns rich product dicts the frontend can render directly
(name, brand, image, price, rating, badges, tags, ...).

Used by the /recommend handler to surface a personalized product rail
alongside the existing offer text.
"""

from __future__ import annotations

import logging

from shared.bedrock import BedrockClientProtocol
from shared.constants import (
    COLLECTION_PRODUCTS,
    COMPLEMENT_PREF_WEIGHT,
    RECOMMEND_KNN_K,
    RECOMMEND_PRODUCTS_LIMIT,
)
from shared.dynamo import DynamoClient
from shared.preference_vector import build_preference_vector
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)


def _is_in_stock(product: dict) -> bool:
    """Storefront products carry `inventoryStatus`. Treat anything not
    explicitly out-of-stock as available — older rows may lack the field."""
    status = (product.get("inventoryStatus") or "").lower()
    return status not in {"out_of_stock", "sold_out", "unavailable"}


def _blend_vectors(
    context_vec: list[float],
    pref_vec: list[float] | None,
    alpha: float,
) -> list[float]:
    if pref_vec is None or alpha <= 0:
        return context_vec
    if alpha >= 1:
        return pref_vec
    return [(1.0 - alpha) * c + alpha * p for c, p in zip(context_vec, pref_vec)]


def _format_product(product: dict, rank: int) -> dict:
    """Trim a storefront row to the fields a product card needs.

    Optional numeric/list fields fall through as None / [] when absent so
    the frontend can rely on the shape without doing presence checks.
    """
    def _opt_float(v):
        try:
            f = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return None
        return f if f > 0 else None

    def _opt_int(v):
        try:
            i = int(v) if v is not None else 0
        except (TypeError, ValueError):
            return None
        return i if i > 0 else None

    return {
        "product_id": product.get("slug") or product.get("id"),
        "name": product.get("name", ""),
        "brand": product.get("brand", ""),
        "category": product.get("category", ""),
        "vertical": product.get("vertical", ""),
        "price": float(product.get("price", 0) or 0),
        "compareAt": _opt_float(product.get("compareAt")),
        "image": product.get("image"),
        "rating": _opt_float(product.get("rating")),
        "reviewCount": _opt_int(product.get("reviewCount")),
        "badges": list(product.get("badges") or []),
        "tags": list(product.get("tags") or []),
        "personalizationTags": list(product.get("personalizationTags") or []),
        "inventoryStatus": product.get("inventoryStatus"),
        "rank": rank,
    }


def pick_personalized_products(
    context: str,
    ranked_facts: list[dict],
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
    dynamo: DynamoClient,
    limit: int = RECOMMEND_PRODUCTS_LIMIT,
) -> dict:
    """Return personalized in-stock products plus the count considered.

    Returns:
        {
            "products": [<formatted product dict>, ...],     # up to `limit`
            "candidates_considered": int,                    # post-DDB-hydrate, pre-stock-filter
        }
    """
    context_vec = bedrock.embed(context)
    pref_vec = build_preference_vector(ranked_facts, bedrock)
    query_vec = _blend_vectors(context_vec, pref_vec, COMPLEMENT_PREF_WEIGHT)

    knn_hits = vectors.search(COLLECTION_PRODUCTS, query_vec, k=RECOMMEND_KNN_K)

    # Preserve KNN order through hydration; de-duplicate slugs.
    candidate_slugs: list[str] = []
    seen: set[str] = set()
    for hit in knn_hits:
        slug = hit.get("id") or hit.get("slug")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        candidate_slugs.append(slug)

    if not candidate_slugs:
        return {"products": [], "candidates_considered": 0}

    fetched = dynamo.batch_get_products(candidate_slugs)
    by_slug = {(p.get("slug") or p.get("id")): p for p in fetched}

    products: list[dict] = []
    considered = 0
    for slug in candidate_slugs:
        p = by_slug.get(slug)
        if not p:
            continue  # OS hit had no DDB row — index drift; skip silently
        considered += 1
        if not _is_in_stock(p):
            continue
        products.append(_format_product(p, len(products) + 1))
        if len(products) >= limit:
            break

    log.info(
        "products_picker: knn=%d considered=%d returned=%d facts_in=%d pref_vec=%s",
        len(knn_hits), considered, len(products), len(ranked_facts),
        pref_vec is not None,
    )
    return {"products": products, "candidates_considered": considered}
