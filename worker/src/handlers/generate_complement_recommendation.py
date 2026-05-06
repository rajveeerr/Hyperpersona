"""Handle generate_complement_recommendation jobs.

Input job payload: {customer_id, cart_items: [...], limit?}
Output: pushes JSON to result:{job_id} for the server to BRPOP.

Personalization:
  Embed a compact summary of the cart, retrieve top customer-facts via
  OpenSearch, ACE-rank them. Pass the cart embedding + the full ranked-fact
  dicts (text + score + polarity) into the complement tool, which builds a
  user-preference vector and runs personalized KNN against the
  product-catalog collection — so customer history actually shapes the
  candidate pool, not just the prompt text.
"""

import json
import logging
import time

from shared.ace_ranking import rank_facts
from shared.constants import COLLECTION_FACTS
from shared.queue import push_result

from ..agents.tools import complement_tool

log = logging.getLogger(__name__)

FACTS_K = 15            # how many candidate facts to pull from OpenSearch
FACTS_TOP = 5           # how many ACE-ranked facts to pass downstream


def _cart_context(products: list[dict]) -> str:
    """Compact text for embedding — drives BOTH customer-facts retrieval and
    the cart side of the candidate KNN, so we only embed once."""
    parts = []
    for p in products:
        name = p.get("name", "")
        descriptor = p.get("subcategory") or p.get("category") or p.get("vertical") or ""
        parts.append(f"{name} ({descriptor})" if descriptor else name)
    return "shopping cart: " + "; ".join(parts)


def _retrieve_ranked_facts(
    customer_id: str,
    cart_vec: list[float],
    vectors,
) -> list[dict]:
    """Return up to FACTS_TOP ACE-ranked fact dicts (text + polarity +
    combined_score). Empty for cold-start customers or on retrieval failure."""
    try:
        raw_facts = vectors.search(
            COLLECTION_FACTS, cart_vec, k=FACTS_K, filter_customer=customer_id,
        )
    except Exception as e:
        log.warning("complement fact retrieval failed: %s", e)
        return []

    ranked, _conflicts = rank_facts(raw_facts)
    return [f for f in ranked[:FACTS_TOP] if f.get("text")]


def handle(job: dict, ctx: dict) -> None:
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

    # Hydrate cart from the lean catalog (unchanged contract — cart_items
    # IDs come in this namespace today).
    cart_products = (
        dynamo.batch_get_recommender_products(cart_items) if cart_items else []
    )

    # Embed cart text once. Reused for facts KNN and for the personalized
    # product-catalog KNN downstream.
    cart_text = _cart_context(cart_products) if cart_products else "empty cart"
    cart_vec = bedrock.embed(cart_text)

    t_facts = time.time()
    ranked_facts = _retrieve_ranked_facts(customer_id, cart_vec, vectors)
    facts_ms = (time.time() - t_facts) * 1000
    tracer.log(
        job_id, "complement", "facts_retrieved",
        {"customer_id": customer_id, "k": FACTS_K, "top": FACTS_TOP},
        {
            "facts_count": len(ranked_facts),
            "facts_preview": [f.get("text", "")[:80] for f in ranked_facts[:2]],
        },
        facts_ms, "ok",
    )

    t0 = time.time()
    result = complement_tool.generate_complement_recommendation(
        customer_id=customer_id,
        cart_item_ids=cart_items,
        cart_vec=cart_vec,
        ranked_facts=ranked_facts,
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
