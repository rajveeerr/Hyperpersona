"""Complementary-products recommender (per-cart reasoning).

Given a customer's cart, recommends products typically bought TOGETHER
(complements) — not similar items (substitutes).

Pipeline:
  1. Hydrate cart products from product_catalog (DDB BatchGetItem)
  2. Pull candidate set: full catalog minus cart items (small catalog;
     for production, filter by category-complementarity instead)
  3. Build a single prompt with cart contents + candidate list
  4. Claude returns ranked JSON of complement product_ids + reasons
  5. Hydrate full product details for the response

Mock-mode behavior: MockBedrockClient.generate returns a stub starting
with "[mock]". We detect that and fall back to a simple heuristic
(top-N from a different category than cart items) so the demo still
produces sensible-looking output.

Why per-cart (not per-item): one Bedrock call instead of N, and Claude
can reason about bundles ("user is building a gaming setup → suggest
gaming keyboard") that per-item can't see.
"""

import json
import logging
import re

from shared.bedrock import BedrockClientProtocol
from shared.dynamo import DynamoClient

log = logging.getLogger(__name__)


_SYSTEM = (
    "You suggest COMPLEMENTARY products — items typically bought TOGETHER "
    "with the cart contents, not similar to them. A laptop and a laptop "
    "bag are complements. A laptop and a tablet are not (those are "
    "substitutes).\n\n"
    "Output JSON only, no prose. Schema:\n"
    '{"recommendations": [{"product_id": "<id>", "reason": "<one short '
    'sentence>", "rank": <1-5>}, ...]}'
)


def _format_product(p: dict) -> str:
    return (
        f"  {p['product_id']:36} {p.get('name', '?')[:38]:38} "
        f"{p.get('subcategory', '?')[:14]:14} ${p.get('price', '?')}"
    )


def _format_cart(cart_products: list[dict]) -> str:
    return "\n".join(
        f"  - {p['name']} (${p.get('price', '?')}, "
        f"{p.get('category', '?')}/{p.get('subcategory', '?')})"
        for p in cart_products
    )


def _build_prompt(
    cart_products: list[dict],
    candidates: list[dict],
    customer_facts: list[str],
    limit: int,
) -> str:
    cart_block = _format_cart(cart_products)
    candidate_block = "\n".join(_format_product(p) for p in candidates)

    facts_block = (
        "\n".join(f"  - {f}" for f in customer_facts)
        if customer_facts else "  (no preferences on file)"
    )

    return (
        f"Cart contents:\n{cart_block}\n\n"
        f"Customer preferences:\n{facts_block}\n\n"
        f"Available products (pick complements from this list ONLY):\n"
        f"{candidate_block}\n\n"
        f"Pick {limit} complementary products ranked by relevance. "
        f"Briefly justify each pick in one sentence."
    )


def _parse_json(generated: str) -> list[dict]:
    """Extract the recommendations array from Claude's response. Returns []
    if parsing fails — caller should treat that as a signal to fall back."""
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


def _heuristic_fallback(
    cart_products: list[dict],
    candidates: list[dict],
    limit: int,
) -> list[dict]:
    """Mock-mode fallback: pick from subcategories NOT in the cart. Gives the
    demo a sensible-looking output without real LLM reasoning.
    """
    cart_subcats = {p.get("subcategory") for p in cart_products}
    other = [c for c in candidates if c.get("subcategory") not in cart_subcats]
    picks = other[:limit] if len(other) >= limit else (other + candidates)[:limit]
    return [
        {
            "product_id": p["product_id"],
            "reason": f"common complement for {cart_products[0].get('subcategory', 'cart')} purchases",
            "rank": i + 1,
        }
        for i, p in enumerate(picks)
    ]


def generate_complement_recommendation(
    customer_id: str,
    cart_item_ids: list[str],
    bedrock: BedrockClientProtocol,
    dynamo: DynamoClient,
    customer_facts: list[str] | None = None,
    limit: int = 5,
) -> dict:
    """Returns {recommendations: [...], cart_items: [...], used_llm: bool,
    cart_resolved: int, candidates_considered: int}."""
    customer_facts = customer_facts or []

    # 1. Resolve cart items
    cart_products = dynamo.batch_get_recommender_products(cart_item_ids) if cart_item_ids else []
    if not cart_products:
        return {
            "recommendations": [],
            "cart_items": cart_item_ids,
            "used_llm": False,
            "cart_resolved": 0,
            "candidates_considered": 0,
        }

    # 2. Candidate pool — full catalog minus cart items (small-catalog assumption)
    cart_id_set = {p["product_id"] for p in cart_products}
    catalog = dynamo.scan_recommender_products()
    candidates = [c for c in catalog if c["product_id"] not in cart_id_set]

    # 3. Ask Claude
    prompt = _build_prompt(cart_products, candidates, customer_facts, limit)
    raw = bedrock.generate(prompt=prompt, system=_SYSTEM, max_tokens=600)

    parsed: list[dict] = []
    used_llm = False
    if not _looks_like_mock(raw):
        parsed = _parse_json(raw)
        used_llm = bool(parsed)

    if not parsed:
        parsed = _heuristic_fallback(cart_products, candidates, limit)

    # 4. Hydrate result with full product details
    cand_by_id = {c["product_id"]: c for c in candidates}
    recommendations: list[dict] = []
    for r in parsed[:limit]:
        pid = r.get("product_id")
        product = cand_by_id.get(pid)
        if not product:
            continue  # Claude hallucinated a product_id not in the catalog
        recommendations.append({
            "product_id": pid,
            "name": product.get("name", ""),
            "category": product.get("category", ""),
            "subcategory": product.get("subcategory", ""),
            "price": float(product.get("price", 0)),
            "reason": r.get("reason", "")[:200],
            "rank": r.get("rank", len(recommendations) + 1),
        })

    log.info(
        "complement: cust=%s cart=%d candidates=%d recs=%d llm=%s",
        customer_id, len(cart_products), len(candidates), len(recommendations), used_llm,
    )
    return {
        "recommendations": recommendations,
        "cart_items": [p["product_id"] for p in cart_products],
        "used_llm": used_llm,
        "cart_resolved": len(cart_products),
        "candidates_considered": len(candidates),
    }
