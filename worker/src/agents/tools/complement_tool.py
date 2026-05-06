"""Complementary-products recommender (per-cart, personalized).

Given a customer's cart and their ACE-ranked preference facts, recommends
products typically bought TOGETHER (complements) — biased toward what this
customer specifically tends to engage with.

Pipeline:
  1. Hydrate cart products from the lean `product_catalog` table (cart_items
     IDs come in this namespace — unchanged from the legacy contract).
  2. Build a user_preference_vector from ACE-ranked facts (polarity-aware).
  3. Blended query vector = (1-α)·cart_vec + α·pref_vec.
  4. KNN against OpenSearch `product-catalog` collection (k=COMPLEMENT_KNN_K).
  5. Hydrate top-K slugs from the storefront `products` table; drop out-of-
     stock; cap at COMPLEMENT_TOP_CANDIDATES.
  6. Pass the enriched candidates to Claude → ranked JSON of complements.

Why two catalogs touch this path: cart_items are received in the legacy
lean-catalog namespace, but the OpenSearch product-catalog index is sourced
from the storefront `products` table (slug-keyed, much richer schema —
description, personalizationTags, inventoryStatus, etc.). Cart-vs-candidate
namespace overlap is left to the prompt instruction ("do not recommend items
already in the cart") rather than a set-difference, since the two id spaces
are not aligned.

Parse-failure fallback: when Claude returns malformed JSON or an empty
rec set, falls back to "top-N from candidates" since they're already
KNN-ranked.
"""

import json
import logging
import re

from shared.bedrock import BedrockClientProtocol
from shared.constants import (
    COLLECTION_PRODUCTS,
    COMPLEMENT_KNN_K,
    COMPLEMENT_PREF_WEIGHT,
    COMPLEMENT_TOP_CANDIDATES,
)
from shared.dynamo import DynamoClient
from shared.preference_vector import build_preference_vector
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)


_SYSTEM = (
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


def _is_in_stock(product: dict) -> bool:
    """Storefront products carry `inventoryStatus`. Treat anything not
    explicitly out-of-stock as available — older rows may lack the field."""
    status = (product.get("inventoryStatus") or "").lower()
    return status not in {"out_of_stock", "sold_out", "unavailable"}


def _blend_vectors(
    cart_vec: list[float],
    pref_vec: list[float] | None,
    alpha: float,
) -> list[float]:
    if pref_vec is None or alpha <= 0:
        return cart_vec
    if alpha >= 1:
        return pref_vec
    return [(1.0 - alpha) * c + alpha * p for c, p in zip(cart_vec, pref_vec)]


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


def _build_prompt(
    cart_products: list[dict],
    candidates: list[dict],
    ranked_facts: list[dict],
    limit: int,
) -> str:
    cart_block = _format_cart(cart_products)
    candidate_block = "\n".join(_format_candidate(p) for p in candidates)

    prefers = [f for f in ranked_facts if (f.get("polarity") or 0) >= 0]
    avoids = [f for f in ranked_facts if (f.get("polarity") or 0) < 0]

    # Number facts (F1, F2, ...) so Claude can cite them via fact_ref.
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

    return (
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
    """Parse-failure fallback: take top N from the KNN-ranked candidate
    list. Candidates are already similarity-sorted, so this is a sensible
    default. Personalization reasons are derived heuristically from
    fact-text ↔ product-attribute overlap."""
    prefers_facts = [
        f for f in ranked_facts if (f.get("polarity") or 0) >= 0 and f.get("text")
    ]
    out: list[dict] = []
    for i, p in enumerate(candidates[:limit]):
        personalization_reason, fact_ref = _match_fact_to_product(p, prefers_facts)
        out.append({
            "product_id": p.get("slug") or p.get("id"),
            "reason": "common complement based on similarity",
            "personalization_reason": personalization_reason,
            "fact_ref": fact_ref,
            "rank": i + 1,
        })
    return out


def _personalized_candidate_search(
    cart_vec: list[float],
    ranked_facts: list[dict],
    vectors: VectorStoreProtocol,
    bedrock: BedrockClientProtocol,
    k: int = COMPLEMENT_KNN_K,
) -> list[dict]:
    """Build blended query vec, run KNN against OpenSearch product-catalog.
    Returns the raw KNN hits (slug + lightweight metadata + similarity)."""
    pref_vec = build_preference_vector(ranked_facts, bedrock)
    query_vec = _blend_vectors(cart_vec, pref_vec, COMPLEMENT_PREF_WEIGHT)
    return vectors.search(COLLECTION_PRODUCTS, query_vec, k=k)


def _hydrate_and_filter(
    knn_hits: list[dict],
    dynamo: DynamoClient,
    top_n: int = COMPLEMENT_TOP_CANDIDATES,
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


def generate_complement_recommendation(
    customer_id: str,
    cart_item_ids: list[str],
    cart_vec: list[float],
    ranked_facts: list[dict],
    bedrock: BedrockClientProtocol,
    dynamo: DynamoClient,
    vectors: VectorStoreProtocol,
    limit: int = 5,
) -> dict:
    """Returns {recommendations, cart_items, used_llm, cart_resolved,
    candidates_considered}."""
    # 1. Resolve cart from lean catalog (unchanged contract).
    cart_products = (
        dynamo.batch_get_recommender_products(cart_item_ids) if cart_item_ids else []
    )
    if not cart_products:
        return {
            "recommendations": [],
            "cart_items": cart_item_ids,
            "used_llm": False,
            "cart_resolved": 0,
            "candidates_considered": 0,
        }

    # 2 + 3. Personalized KNN against storefront product-catalog.
    knn_hits = _personalized_candidate_search(
        cart_vec=cart_vec,
        ranked_facts=ranked_facts,
        vectors=vectors,
        bedrock=bedrock,
    )

    # 4. Hydrate candidates from storefront `products` + filter.
    candidates = _hydrate_and_filter(knn_hits=knn_hits, dynamo=dynamo)

    if not candidates:
        return {
            "recommendations": [],
            "cart_items": [p.get("product_id") for p in cart_products],
            "used_llm": False,
            "cart_resolved": len(cart_products),
            "candidates_considered": 0,
        }

    # 5. Ask Claude.
    prompt = _build_prompt(cart_products, candidates, ranked_facts, limit)
    raw = bedrock.generate(prompt=prompt, system=_SYSTEM, max_tokens=600)

    parsed = _parse_json(raw)
    used_llm = bool(parsed)

    if not parsed:
        # Claude returned malformed JSON or an empty rec set — fall back to
        # the deterministic heuristic so the rail still renders something.
        parsed = _heuristic_fallback(candidates, ranked_facts, limit)

    # 6. Hydrate result with full product details.
    cand_by_slug = {(c.get("slug") or c.get("id")): c for c in candidates}
    recommendations: list[dict] = []
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

        recommendations.append({
            "product_id": pid,
            "name": product.get("name", ""),
            "category": product.get("category", ""),
            "vertical": product.get("vertical", ""),
            "price": float(product.get("price", 0) or 0),
            "reason": (r.get("reason") or "")[:200],
            "personalization_reason": pr,
            "fact_ref": fact_ref,
            "rank": r.get("rank", len(recommendations) + 1),
        })

    log.info(
        "complement: cust=%s cart=%d candidates=%d recs=%d llm=%s",
        customer_id, len(cart_products), len(candidates), len(recommendations), used_llm,
    )
    return {
        "recommendations": recommendations,
        "cart_items": [p.get("product_id") for p in cart_products],
        "used_llm": used_llm,
        "cart_resolved": len(cart_products),
        "candidates_considered": len(candidates),
    }
