"""Handle generate_related_recommendation jobs (both modes).

One handler serves two endpoints; the `mode` field in the payload picks the
seed strategy:

  mode="complement"  → /recommend/complement
        Payload: {customer_id, cart_items: [...], limit, mode}
        Seed:    cart text (compact summary of cart contents) → bedrock.embed

  mode="substitute"  → /recommend/similar-price
        Payload: {customer_id, product_id, tolerance, limit, mode}
        Seed:    anchor product text → bedrock.embed
                 + computed price band [price * (1 - tol), price * (1 + tol)]

Once the seed vector exists, both modes:
  1. Retrieve top customer-facts via OpenSearch + ACE-rank.
  2. Pass everything into related_recommender_tool, which branches internally
     for KNN filters, prompt framing, and post-hydrate filtering.
  3. Build a top-level "Because you ..." personalization heading from the
     facts and push the merged result to result:{job_id}.
"""

import json
import logging
import time

from shared.constants import SIMILAR_PRICE_DEFAULT_TOLERANCE
from shared.queue import push_result

from ..agents.tools import related_recommender_tool
from ..agents.tools._product_reco_helpers import (
    build_personalization_reason,
    retrieve_ranked_facts,
)

log = logging.getLogger(__name__)


def _cart_context(products: list[dict]) -> str:
    """Compact cart text for embedding — drives BOTH customer-facts retrieval
    and the cart side of the candidate KNN, so we only embed once."""
    parts = []
    for p in products:
        name = p.get("name", "")
        descriptor = (
            p.get("subcategory") or p.get("category") or p.get("vertical") or ""
        )
        parts.append(f"{name} ({descriptor})" if descriptor else name)
    return "shopping cart: " + "; ".join(parts)


def _anchor_context(anchor: dict) -> str:
    """Compact anchor text for embedding — analogous to _cart_context but
    for a single product. The richer anchor row carries brand and tags, so
    we use them to give the seed more topical signal than the cart version."""
    parts = [anchor.get("name", "")]
    if anchor.get("brand"):
        parts.append(f"by {anchor['brand']}")
    if anchor.get("category"):
        parts.append(f"({anchor['category']})")
    suffix = " ".join(p for p in parts if p)
    tags = anchor.get("tags") or []
    if tags:
        suffix += "; tags: " + ", ".join(str(t) for t in tags[:8])
    return f"product: {suffix}"


def _handle_complement(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    cart_items = list(payload.get("cart_items") or [])
    limit = int(payload.get("limit", 5))

    bedrock = ctx["bedrock"]
    dynamo = ctx["dynamo"]
    vectors = ctx["vectors"]
    redis_client = ctx["redis"]
    tracer = ctx["tracer"]

    tracer.log(
        job_id, "supervisor", "start_complement",
        {"customer_id": customer_id, "cart_size": len(cart_items)},
        {}, 0.0, "ok",
    )

    cart_products = (
        dynamo.batch_get_recommender_products(cart_items) if cart_items else []
    )

    cart_text = _cart_context(cart_products) if cart_products else "empty cart"
    seed_vec = bedrock.embed(cart_text)

    t_facts = time.time()
    ranked_facts = retrieve_ranked_facts(customer_id, seed_vec, vectors)
    facts_ms = (time.time() - t_facts) * 1000
    tracer.log(
        job_id, "complement", "facts_retrieved",
        {"customer_id": customer_id},
        {
            "facts_count": len(ranked_facts),
            "facts_preview": [f.get("text", "")[:80] for f in ranked_facts[:2]],
        },
        facts_ms, "ok",
    )

    t0 = time.time()
    result = related_recommender_tool.generate_related_recommendation(
        mode="complement",
        customer_id=customer_id,
        seed_vec=seed_vec,
        ranked_facts=ranked_facts,
        cart_products=cart_products,
        cart_item_ids=cart_items,
        bedrock=bedrock,
        dynamo=dynamo,
        vectors=vectors,
        limit=limit,
    )
    duration_ms = (time.time() - t0) * 1000

    tracer.log(
        job_id, "complement", "generate_complement",
        {"cart_size": len(cart_items), "limit": limit, "facts_used": len(ranked_facts)},
        {
            "recommendations": len(result["recommendations"]),
            "candidates_considered": result["candidates_considered"],
            "used_llm": result["used_llm"],
        },
        duration_ms, "ok",
    )

    result["facts_used"] = len(ranked_facts)
    result["personalization_reason"] = build_personalization_reason(ranked_facts)
    push_result(redis_client, job_id, json.dumps({**result, "job_id": job_id}))
    tracer.log(
        job_id, "supervisor", "end_complement",
        {}, {"recs_returned": len(result["recommendations"])},
        0.0, "ok",
    )
    log.info(
        "complement result pushed for job %s (facts=%d, recs=%d, llm=%s)",
        job_id, len(ranked_facts), len(result["recommendations"]), result["used_llm"],
    )


def _handle_substitute(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    product_id = payload["product_id"]
    limit = int(payload.get("limit", 6))
    tolerance = float(payload.get("tolerance", SIMILAR_PRICE_DEFAULT_TOLERANCE))

    bedrock = ctx["bedrock"]
    dynamo = ctx["dynamo"]
    vectors = ctx["vectors"]
    redis_client = ctx["redis"]
    tracer = ctx["tracer"]

    tracer.log(
        job_id, "supervisor", "start_substitute",
        {"customer_id": customer_id, "product_id": product_id, "tolerance": tolerance},
        {}, 0.0, "ok",
    )

    # Resolve the anchor product from storefront `products`. If the slug is
    # unknown, return an empty rail rather than 500-ing — the frontend can
    # fall back to a generic recommendation.
    anchors = dynamo.batch_get_products([product_id])
    if not anchors:
        empty = {
            "products": [],
            "anchor_product_id": product_id,
            "anchor_price": 0.0,
            "price_band": {"min": 0.0, "max": 0.0},
            "candidates_considered": 0,
            "candidates_dropped_low_review": 0,
            "candidates_dropped_off_category": 0,
            "category_lock_relaxed": False,
            "used_llm": False,
            "personalization_reason": None,
            "facts_used": 0,
            "job_id": job_id,
        }
        push_result(redis_client, job_id, json.dumps(empty))
        tracer.log(
            job_id, "supervisor", "end_substitute",
            {}, {"anchor_resolved": False}, 0.0, "ok",
        )
        log.info("substitute: anchor not found product_id=%s job=%s", product_id, job_id)
        return
    anchor = anchors[0]
    anchor_price = float(anchor.get("price") or 0)
    price_band = (anchor_price * (1 - tolerance), anchor_price * (1 + tolerance))

    anchor_text = _anchor_context(anchor)
    seed_vec = bedrock.embed(anchor_text)

    t_facts = time.time()
    ranked_facts = retrieve_ranked_facts(customer_id, seed_vec, vectors)
    facts_ms = (time.time() - t_facts) * 1000
    tracer.log(
        job_id, "substitute", "facts_retrieved",
        {"customer_id": customer_id},
        {
            "facts_count": len(ranked_facts),
            "facts_preview": [f.get("text", "")[:80] for f in ranked_facts[:2]],
        },
        facts_ms, "ok",
    )

    t0 = time.time()
    result = related_recommender_tool.generate_related_recommendation(
        mode="substitute",
        customer_id=customer_id,
        seed_vec=seed_vec,
        ranked_facts=ranked_facts,
        anchor=anchor,
        price_band=price_band,
        bedrock=bedrock,
        dynamo=dynamo,
        vectors=vectors,
        limit=limit,
    )
    duration_ms = (time.time() - t0) * 1000

    tracer.log(
        job_id, "substitute", "generate_substitute",
        {
            "product_id": product_id,
            "limit": limit,
            "tolerance": tolerance,
            "facts_used": len(ranked_facts),
        },
        {
            "products": len(result["products"]),
            "candidates_considered": result["candidates_considered"],
            "candidates_dropped_low_review": result["candidates_dropped_low_review"],
            "candidates_dropped_off_category": result["candidates_dropped_off_category"],
            "category_lock_relaxed": result["category_lock_relaxed"],
            "used_llm": result["used_llm"],
        },
        duration_ms, "ok",
    )

    result["facts_used"] = len(ranked_facts)
    result["personalization_reason"] = build_personalization_reason(ranked_facts)
    push_result(redis_client, job_id, json.dumps({**result, "job_id": job_id}))
    tracer.log(
        job_id, "supervisor", "end_substitute",
        {}, {"products_returned": len(result["products"])},
        0.0, "ok",
    )
    log.info(
        "substitute result pushed for job %s (anchor=%s facts=%d products=%d llm=%s)",
        job_id, product_id, len(ranked_facts), len(result["products"]), result["used_llm"],
    )


def handle(job: dict, ctx: dict) -> None:
    """Dispatch on the payload's `mode` field. Defaults to complement for
    backward-compat with any pre-rename in-flight jobs."""
    mode = (job.get("payload") or {}).get("mode", "complement")
    if mode == "substitute":
        _handle_substitute(job, ctx)
    else:
        _handle_complement(job, ctx)
