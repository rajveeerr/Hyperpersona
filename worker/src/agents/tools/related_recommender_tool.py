"""Related-products recommender — unified pipeline for two endpoints.

Two product rails share ~80% of this code, so they share the implementation:

  - mode="complement"  → /recommend/complement
        Cart-driven. Find products typically bought TOGETHER with the cart
        contents (laptop → laptop bag). Different category, paired use.

  - mode="substitute"  → /recommend/similar-price
        Anchor-driven. Find products in the SAME category at a similar price
        (iPhone → Pixel). Same category, competing alternative.

Both paths:
  1. Build a personalized query vector: blend(seed_vec, preference_vec)
     where preference_vec is built from ACE-ranked customer facts.
  2. KNN against OpenSearch `product-catalog` (mode-specific filters apply).
  3. Hydrate top hits from storefront `products` table; drop OOS.
  4. Mode-specific post-hydrate filtering (substitute: review floor +
     belt-and-suspenders category lock; complement: pass-through).
  5. Ask Claude to rank with per-pick reasons (mode-specific prompt).
  6. On parse failure / mock mode, fall back to top-N by KNN similarity.

Substitute mode hard-locks to the anchor's category at the OpenSearch level
(term filter), with a vertical-locked fallback only when the strict pool is
starved. The post-hydrate check then drops any leakage. Prompt language
explicitly forbids accessories — three layers of defense against
accidentally returning complements.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from shared.bedrock import BedrockClientProtocol
from shared.constants import (
    COLLECTION_PRODUCTS,
    COMPLEMENT_KNN_K,
    COMPLEMENT_PREF_WEIGHT,
    COMPLEMENT_TOP_CANDIDATES,
    MIN_RATING_FOR_RECOMMENDATION,
    MIN_REVIEW_COUNT_FOR_RECOMMENDATION,
    SIMILAR_PRICE_FALLBACK_THRESHOLD,
    SIMILAR_PRICE_KNN_K,
    SIMILAR_PRICE_PREF_WEIGHT,
    SIMILAR_PRICE_TOP_CANDIDATES,
)
from shared.dynamo import DynamoClient
from shared.preference_vector import build_preference_vector
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)


Mode = Literal["complement", "substitute"]


# ─────────────────────────────────────────────────────────────────────────────
# System prompts — flipped framing per mode
# ─────────────────────────────────────────────────────────────────────────────

_COMPLEMENT_SYSTEM = (
    "You suggest COMPLEMENTARY products — items typically bought TOGETHER "
    "with the cart contents, not similar to them. A laptop and a laptop "
    "bag are complements. A laptop and a tablet are not (those are "
    "substitutes). Never recommend something already in the cart.\n\n"
    "For each pick, also write a personalization_reason in 2nd person "
    '("Because you ...") that cites a specific Customer-prefers fact when '
    'one applies. Use null when no fact justifies a personal tie. Keep it '
    "under 90 characters. Reference the matching fact id (e.g. F2) in "
    "fact_ref, or null if none.\n\n"
    "Output JSON only, no prose. Schema:\n"
    '{"recommendations": [{"product_id": "<slug>", "reason": "<one short '
    'sentence>", "personalization_reason": "<2nd-person sentence or null>", '
    '"fact_ref": "<F1|F2|...|null>", "rank": <1-5>}, ...]}'
)

_SUBSTITUTE_SYSTEM = (
    "You suggest SUBSTITUTES — products the customer could buy INSTEAD OF "
    "the anchor. Same category, comparable price tier, competing "
    "alternative. NEVER recommend complements (accessories, paired-use "
    "items): if the anchor is a phone, do NOT recommend cases, chargers, "
    "or earbuds; if it's a laptop, do NOT recommend bags, mice, or "
    "sleeves. Recommend only OTHER PHONES / OTHER LAPTOPS in the same "
    "price band. Never recommend the anchor itself.\n\n"
    "For each pick, write reason as ONE short sentence explaining what "
    "makes this a viable alternative to the anchor (e.g. 'Comparable "
    "Android flagship at the same price tier with stronger telephoto'). "
    "Also write a personalization_reason in 2nd person "
    '("Because you ...") that cites a specific Customer-prefers fact when '
    "one applies. Use null when no fact justifies a personal tie. Keep it "
    "under 90 characters. Reference the matching fact id (e.g. F2) in "
    "fact_ref, or null if none.\n\n"
    "Output JSON only, no prose. Schema:\n"
    '{"recommendations": [{"product_id": "<slug>", "reason": "<one short '
    'sentence>", "personalization_reason": "<2nd-person sentence or null>", '
    '"fact_ref": "<F1|F2|...|null>", "rank": <1-5>}, ...]}'
)


# ─────────────────────────────────────────────────────────────────────────────
# Small utilities (unchanged from the pre-rename complement_tool.py)
# ─────────────────────────────────────────────────────────────────────────────

def _is_in_stock(product: dict) -> bool:
    """Storefront products carry `inventoryStatus`. Treat anything not
    explicitly out-of-stock as available — older rows may lack the field."""
    status = (product.get("inventoryStatus") or "").lower()
    return status not in {"out_of_stock", "sold_out", "unavailable"}


def _blend_vectors(
    seed_vec: list[float],
    pref_vec: list[float] | None,
    alpha: float,
) -> list[float]:
    if pref_vec is None or alpha <= 0:
        return seed_vec
    if alpha >= 1:
        return pref_vec
    return [(1.0 - alpha) * c + alpha * p for c, p in zip(seed_vec, pref_vec)]


def _format_candidate(p: dict) -> str:
    bits = [
        f"id={p.get('slug') or p.get('id', '?')}",
        f"name={(p.get('name') or '?')[:60]}",
    ]
    if p.get("brand"):
        bits.append(f"brand={p['brand']}")
    if p.get("category"):
        bits.append(f"cat={p['category']}")
    if p.get("vertical"):
        bits.append(f"vert={p['vertical']}")
    bits.append(f"${p.get('price', '?')}")
    rating = p.get("rating")
    if rating:
        bits.append(f"rating={rating}")
    tags = p.get("tags") or []
    if tags:
        bits.append(f"tags={','.join(str(t) for t in tags[:5])}")
    ptags = p.get("personalizationTags") or []
    if ptags:
        bits.append(f"persona={','.join(str(t) for t in ptags[:5])}")
    desc = (p.get("description") or "")[:100]
    if desc:
        bits.append(f"desc={desc}")
    return "  - " + " | ".join(bits)


def _format_cart(cart_products: list[dict]) -> str:
    """Cart products come from the lean catalog → use category/subcategory."""
    return "\n".join(
        f"  - {p.get('name', '?')} (${p.get('price', '?')}, "
        f"{p.get('category', '?')}/{p.get('subcategory', '?')})"
        for p in cart_products
    )


def _format_anchor(anchor: dict) -> str:
    """Anchor comes from the storefront `products` table — has more fields
    than a lean cart row, so we lean on the same shape complement candidates
    use to keep prompt formatting consistent."""
    bits = [
        f"id={anchor.get('slug') or anchor.get('id', '?')}",
        f"name={anchor.get('name', '?')}",
    ]
    if anchor.get("brand"):
        bits.append(f"brand={anchor['brand']}")
    if anchor.get("category"):
        bits.append(f"cat={anchor['category']}")
    if anchor.get("vertical"):
        bits.append(f"vert={anchor['vertical']}")
    bits.append(f"${anchor.get('price', '?')}")
    return "  - " + " | ".join(bits)


def _parse_json(generated: str) -> list[dict]:
    """Extract the recommendations array from Claude's response. Returns []
    if parsing fails — caller treats that as a signal to fall back."""
    match = re.search(r"\{.*\}", generated, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
        recs = parsed.get("recommendations") or []
        return [r for r in recs if isinstance(r, dict) and "product_id" in r]
    except (json.JSONDecodeError, ValueError):
        return []


def _looks_like_mock(text: str) -> bool:
    return text.strip().startswith("[mock]")


def _match_fact_to_product(
    product: dict,
    prefers_facts: list[dict],
) -> tuple[str | None, str | None]:
    """Best-effort fact-to-product match for the heuristic / fallback.
    Returns (personalization_reason, fact_ref) or (None, None) if no match.

    Match logic: a Prefers fact "matches" a product if the fact's lowercased
    text contains the product's brand, category, vertical, or any
    personalizationTag/tag as a substring. Picks the first hit in fact rank
    order — Prefers is already ACE-sorted by combined_score.
    """
    if not prefers_facts:
        return None, None

    haystacks = [
        product.get("brand"),
        product.get("category"),
        product.get("vertical"),
        *(product.get("personalizationTags") or []),
        *(product.get("tags") or []),
    ]
    needles = [str(h).lower() for h in haystacks if h]
    if not needles:
        return None, None

    for i, fact in enumerate(prefers_facts):
        text = (fact.get("text") or "").lower()
        if not text:
            continue
        if any(n in text for n in needles):
            reason = f"Because you {fact.get('text', '').strip()}"
            return reason[:90], f"F{i+1}"
    return None, None


def _heuristic_fallback(
    candidates: list[dict],
    ranked_facts: list[dict],
    limit: int,
) -> list[dict]:
    """Mock-mode / parse-failure fallback: take top N from the KNN-ranked
    candidate list. Candidates are already similarity-sorted, so this is a
    sensible default. Personalization reasons are derived heuristically from
    fact-text ↔ product-attribute overlap."""
    prefers_facts = [
        f for f in ranked_facts if (f.get("polarity") or 0) >= 0 and f.get("text")
    ]
    out: list[dict] = []
    for i, p in enumerate(candidates[:limit]):
        personalization_reason, fact_ref = _match_fact_to_product(p, prefers_facts)
        out.append({
            "product_id": p.get("slug") or p.get("id"),
            "reason": "common pick based on similarity",
            "personalization_reason": personalization_reason,
            "fact_ref": fact_ref,
            "rank": i + 1,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Mode-aware private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pref_weight_for(mode: Mode) -> float:
    return COMPLEMENT_PREF_WEIGHT if mode == "complement" else SIMILAR_PRICE_PREF_WEIGHT


def _knn_k_for(mode: Mode) -> int:
    return COMPLEMENT_KNN_K if mode == "complement" else SIMILAR_PRICE_KNN_K


def _top_candidates_for(mode: Mode) -> int:
    return COMPLEMENT_TOP_CANDIDATES if mode == "complement" else SIMILAR_PRICE_TOP_CANDIDATES


def _run_knn_for_mode(
    *,
    mode: Mode,
    vectors: VectorStoreProtocol,
    query_vec: list[float],
    anchor: dict | None,
    price_band: tuple[float, float] | None,
) -> tuple[list[dict], bool]:
    """Run the KNN search with mode-appropriate filters.

    Returns (knn_hits, category_lock_relaxed). category_lock_relaxed is only
    meaningful for substitute mode; always False for complement.
    """
    k = _knn_k_for(mode)
    if mode == "complement":
        return vectors.search(COLLECTION_PRODUCTS, query_vec, k=k), False

    # Substitute: lock to anchor.category + price band as the primary gate.
    assert anchor is not None and price_band is not None
    min_p, max_p = price_band
    range_filter = {"price": {"gte": float(min_p), "lte": float(max_p)}}

    category = anchor.get("category")
    vertical = anchor.get("vertical")

    if category:
        hits = vectors.search(
            COLLECTION_PRODUCTS, query_vec, k=k,
            term_filters={"category": category},
            range_filter=range_filter,
        )
        if len(hits) >= SIMILAR_PRICE_FALLBACK_THRESHOLD or not vertical:
            return hits, False

        log.info(
            "substitute KNN: strict category=%s yielded %d hits (<%d), "
            "relaxing to vertical=%s",
            category, len(hits), SIMILAR_PRICE_FALLBACK_THRESHOLD, vertical,
        )

    # Either no category on anchor, or strict pool too small → vertical lock.
    if vertical:
        return vectors.search(
            COLLECTION_PRODUCTS, query_vec, k=k,
            term_filters={"vertical": vertical},
            range_filter=range_filter,
        ), True

    # Extreme edge: anchor has neither category nor vertical. Fall back to
    # price-only — better than nothing, and the post-hydrate check still
    # gates on the lock_field if we can derive one.
    return vectors.search(
        COLLECTION_PRODUCTS, query_vec, k=k, range_filter=range_filter,
    ), True


def _hydrate_and_filter(
    knn_hits: list[dict],
    dynamo: DynamoClient,
    top_n: int,
) -> list[dict]:
    """Hydrate KNN hits from storefront `products` and drop out-of-stock.
    Preserves KNN order through the hydration step."""
    # Prefer metadata `slug` over the doc-`id`: AOSS auto-generates opaque ids
    # (see shared/opensearch.py upsert), so falling back to `id` produces
    # garbage slugs that will never match the storefront DDB rows. Local
    # OpenSearch keeps doc_id == slug, so the `id` fallback still works there.
    candidate_slugs: list[str] = []
    seen: set[str] = set()
    for hit in knn_hits:
        slug = hit.get("slug") or hit.get("id")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        candidate_slugs.append(slug)

    if not candidate_slugs:
        return []

    fetched = dynamo.batch_get_products(candidate_slugs)
    by_slug = {(p.get("slug") or p.get("id")): p for p in fetched}

    filtered: list[dict] = []
    for slug in candidate_slugs:
        p = by_slug.get(slug)
        if not p:
            continue  # OS hit had no DDB row — index drift; skip silently
        if not _is_in_stock(p):
            continue
        filtered.append(p)
        if len(filtered) >= top_n:
            break

    return filtered


def _apply_substitute_floor(
    candidates: list[dict],
    *,
    anchor: dict,
    lock_field: str,
) -> tuple[list[dict], int, int]:
    """Substitute-mode quality gate. Drops:
      - the anchor itself
      - off-category items that slipped past the OpenSearch term filter
      - items below MIN_RATING_FOR_RECOMMENDATION
      - items below MIN_REVIEW_COUNT_FOR_RECOMMENDATION

    Returns (kept, dropped_low_review, dropped_off_category).
    """
    anchor_slug = anchor.get("slug") or anchor.get("id")
    anchor_lock = anchor.get(lock_field)

    kept: list[dict] = []
    dropped_low_review = 0
    dropped_off_category = 0

    for p in candidates:
        slug = p.get("slug") or p.get("id")
        if slug == anchor_slug:
            continue

        if anchor_lock and p.get(lock_field) != anchor_lock:
            dropped_off_category += 1
            continue

        rating = float(p.get("rating") or 0)
        review_count = int(p.get("reviewCount") or 0)
        if rating < MIN_RATING_FOR_RECOMMENDATION or review_count < MIN_REVIEW_COUNT_FOR_RECOMMENDATION:
            dropped_low_review += 1
            continue

        kept.append(p)

    return kept, dropped_low_review, dropped_off_category


def _build_prompt_for_mode(
    *,
    mode: Mode,
    ranked_facts: list[dict],
    candidates: list[dict],
    cart_products: list[dict] | None,
    anchor: dict | None,
    limit: int,
) -> tuple[str, str]:
    """Assemble (user_prompt, system_prompt) for the given mode."""
    candidate_block = "\n".join(_format_candidate(p) for p in candidates)

    prefers = [f for f in ranked_facts if (f.get("polarity") or 0) >= 0]
    avoids = [f for f in ranked_facts if (f.get("polarity") or 0) < 0]
    prefers_block = (
        "\n".join(
            f"  F{i+1}: {f.get('text', '')}" for i, f in enumerate(prefers)
        )
        if prefers else "  (none on file)"
    )
    avoids_block = (
        "\n".join(f"  - {f.get('text', '')}" for f in avoids)
        if avoids else "  (none on file)"
    )

    if mode == "complement":
        cart_block = _format_cart(cart_products or [])
        user = (
            f"Cart contents (do NOT recommend any of these):\n{cart_block}\n\n"
            f"Customer prefers:\n{prefers_block}\n\n"
            f"Customer avoids:\n{avoids_block}\n\n"
            f"Available products (pick complements from this list ONLY):\n"
            f"{candidate_block}\n\n"
            f"Pick {limit} complementary products ranked by relevance. "
            f"For each, write a one-sentence reason explaining the pairing, plus "
            f"a personalization_reason in 2nd person citing a Prefers fact when "
            f"applicable (or null), plus a fact_ref like F1/F2 or null."
        )
        return user, _COMPLEMENT_SYSTEM

    # substitute
    assert anchor is not None
    anchor_block = _format_anchor(anchor)
    user = (
        f"Anchor product (the one the customer is viewing — do NOT recommend it):\n"
        f"{anchor_block}\n\n"
        f"Customer prefers:\n{prefers_block}\n\n"
        f"Customer avoids:\n{avoids_block}\n\n"
        f"Available substitutes (pick from this list ONLY — these are already "
        f"category-locked and price-banded for you):\n{candidate_block}\n\n"
        f"Pick {limit} substitute products ranked by how well each works as an "
        f"alternative to the anchor. For each, write a one-sentence reason "
        f"explaining what makes it a viable alternative (don't just describe "
        f"the product — compare it to the anchor). Plus a personalization_reason "
        f"in 2nd person citing a Prefers fact when applicable (or null), plus "
        f"a fact_ref like F1/F2 or null."
    )
    return user, _SUBSTITUTE_SYSTEM


def _format_recommendations(
    parsed: list[dict],
    candidates: list[dict],
    ranked_facts: list[dict],
    limit: int,
) -> list[dict]:
    """Hydrate Claude's picks (or the heuristic fallback's) with full product
    details from the candidate set. Format matches the rail-card shape used
    by /recommend so the frontend product card renders identically across
    both endpoints."""
    cand_by_slug = {(c.get("slug") or c.get("id")): c for c in candidates}
    out: list[dict] = []

    for r in parsed[:limit]:
        pid = r.get("product_id")
        product = cand_by_slug.get(pid)
        if not product:
            continue  # Claude hallucinated a slug not in the candidate set

        # personalization_reason: take Claude's value if present, else heuristic
        # match against ranked_facts. Always carried through (None when no
        # personal tie applies).
        pr = r.get("personalization_reason")
        if pr is None or (isinstance(pr, str) and not pr.strip()):
            prefers = [
                f for f in ranked_facts
                if (f.get("polarity") or 0) >= 0 and f.get("text")
            ]
            pr, fact_ref = _match_fact_to_product(product, prefers)
        else:
            pr = pr.strip()[:90]
            fact_ref = r.get("fact_ref")
            if fact_ref is not None and not isinstance(fact_ref, str):
                fact_ref = None

        out.append({
            "product_id": pid,
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "vertical": product.get("vertical", ""),
            "price": float(product.get("price", 0) or 0),
            "image": product.get("image"),
            "rating": float(product.get("rating") or 0) or None,
            "reviewCount": int(product.get("reviewCount") or 0) or None,
            "badges": list(product.get("badges") or []),
            "tags": list(product.get("tags") or []),
            "personalizationTags": list(product.get("personalizationTags") or []),
            "inventoryStatus": product.get("inventoryStatus"),
            "reason": (r.get("reason") or "")[:200],
            "personalization_reason": pr,
            "fact_ref": fact_ref,
            "rank": r.get("rank", len(out) + 1),
        })

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point — single mode-aware function
# ─────────────────────────────────────────────────────────────────────────────

def generate_related_recommendation(
    *,
    mode: Mode,
    customer_id: str,
    seed_vec: list[float],
    ranked_facts: list[dict],
    bedrock: BedrockClientProtocol,
    dynamo: DynamoClient,
    vectors: VectorStoreProtocol,
    limit: int = 5,
    # complement-only:
    cart_products: list[dict] | None = None,
    cart_item_ids: list[str] | None = None,
    # substitute-only:
    anchor: dict | None = None,
    price_band: tuple[float, float] | None = None,
) -> dict:
    """Run the related-recommender for either mode.

    Returns a dict whose keys differ by mode:

      complement → {recommendations, cart_items, cart_resolved,
                    candidates_considered, used_llm}

      substitute → {products, anchor_product_id, anchor_price, price_band,
                    candidates_considered, candidates_dropped_low_review,
                    candidates_dropped_off_category, category_lock_relaxed,
                    used_llm}
    """
    if mode == "complement":
        if cart_products is None:
            raise ValueError("complement mode requires cart_products")
    elif mode == "substitute":
        if anchor is None or price_band is None:
            raise ValueError("substitute mode requires anchor and price_band")
    else:
        raise ValueError(f"unknown mode: {mode!r}")

    # Cart-not-resolved early return mirrors complement_tool's prior behavior.
    if mode == "complement" and not cart_products:
        return {
            "recommendations": [],
            "cart_items": list(cart_item_ids or []),
            "cart_resolved": 0,
            "candidates_considered": 0,
            "used_llm": False,
        }

    # 1. Personalized KNN.
    pref_vec = build_preference_vector(ranked_facts, bedrock)
    query_vec = _blend_vectors(seed_vec, pref_vec, _pref_weight_for(mode))
    knn_hits, category_lock_relaxed = _run_knn_for_mode(
        mode=mode, vectors=vectors, query_vec=query_vec,
        anchor=anchor, price_band=price_band,
    )

    # 2. Hydrate from storefront, drop OOS.
    candidates = _hydrate_and_filter(
        knn_hits=knn_hits, dynamo=dynamo, top_n=_top_candidates_for(mode),
    )

    # 3. Mode-specific post-hydrate filtering.
    dropped_low_review = 0
    dropped_off_category = 0
    if mode == "substitute":
        candidates, dropped_low_review, dropped_off_category = _apply_substitute_floor(
            candidates,
            anchor=anchor,  # type: ignore[arg-type]
            lock_field="vertical" if category_lock_relaxed else "category",
        )

    if not candidates:
        return _empty_result(
            mode=mode,
            cart_products=cart_products,
            cart_item_ids=cart_item_ids,
            anchor=anchor,
            price_band=price_band,
            dropped_low_review=dropped_low_review,
            dropped_off_category=dropped_off_category,
            category_lock_relaxed=category_lock_relaxed,
        )

    # 4. Prompt + Claude.
    prompt, system = _build_prompt_for_mode(
        mode=mode, ranked_facts=ranked_facts, candidates=candidates,
        cart_products=cart_products, anchor=anchor, limit=limit,
    )
    raw = bedrock.generate(prompt=prompt, system=system, max_tokens=600)

    # 5. Parse + fallback.
    parsed: list[dict] = []
    used_llm = False
    if not _looks_like_mock(raw):
        parsed = _parse_json(raw)
        used_llm = bool(parsed)
    if not parsed:
        parsed = _heuristic_fallback(candidates, ranked_facts, limit)

    # 6. Hydrate result with full product details.
    products = _format_recommendations(parsed, candidates, ranked_facts, limit)

    if mode == "complement":
        log.info(
            "related complement: cust=%s cart=%d candidates=%d recs=%d llm=%s",
            customer_id, len(cart_products or []), len(candidates),
            len(products), used_llm,
        )
        return {
            "recommendations": products,
            "cart_items": [p.get("product_id") for p in (cart_products or [])],
            "cart_resolved": len(cart_products or []),
            "candidates_considered": len(candidates),
            "used_llm": used_llm,
        }

    # substitute
    assert anchor is not None and price_band is not None
    log.info(
        "related substitute: cust=%s anchor=%s candidates=%d dropped_review=%d "
        "dropped_off_cat=%d relaxed=%s recs=%d llm=%s",
        customer_id, anchor.get("slug") or anchor.get("id"),
        len(candidates), dropped_low_review, dropped_off_category,
        category_lock_relaxed, len(products), used_llm,
    )
    return {
        "products": products,
        "anchor_product_id": anchor.get("slug") or anchor.get("id"),
        "anchor_price": float(anchor.get("price") or 0),
        "price_band": {"min": float(price_band[0]), "max": float(price_band[1])},
        "candidates_considered": len(candidates),
        "candidates_dropped_low_review": dropped_low_review,
        "candidates_dropped_off_category": dropped_off_category,
        "category_lock_relaxed": category_lock_relaxed,
        "used_llm": used_llm,
    }


def _empty_result(
    *,
    mode: Mode,
    cart_products: list[dict] | None,
    cart_item_ids: list[str] | None,
    anchor: dict | None,
    price_band: tuple[float, float] | None,
    dropped_low_review: int,
    dropped_off_category: int,
    category_lock_relaxed: bool,
) -> dict:
    if mode == "complement":
        return {
            "recommendations": [],
            "cart_items": [p.get("product_id") for p in (cart_products or [])] or list(cart_item_ids or []),
            "cart_resolved": len(cart_products or []),
            "candidates_considered": 0,
            "used_llm": False,
        }
    assert anchor is not None
    return {
        "products": [],
        "anchor_product_id": anchor.get("slug") or anchor.get("id"),
        "anchor_price": float(anchor.get("price") or 0),
        "price_band": (
            {"min": float(price_band[0]), "max": float(price_band[1])}
            if price_band else {"min": 0.0, "max": 0.0}
        ),
        "candidates_considered": 0,
        "candidates_dropped_low_review": dropped_low_review,
        "candidates_dropped_off_category": dropped_off_category,
        "category_lock_relaxed": category_lock_relaxed,
        "used_llm": False,
    }
