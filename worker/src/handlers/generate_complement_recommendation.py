"""Handle generate_complement_recommendation jobs.

Input job payload: {customer_id, cart_items: [...], limit?}
Output: pushes JSON to result:{job_id} for the server to BRPOP.

Personalization (Stage 3):
  Embed a compact summary of the cart, retrieve top customer-facts via
  OpenSearch, ACE-rank them, and pass the top texts into the complement
  tool so Claude can prefer items matching past behaviour. In mock mode
  the LLM falls back to the heuristic (no fact reasoning), but the wiring
  is in place — flips on automatically with real Bedrock.
"""

import json
import logging
import time

from shared.ace_ranking import rank_facts
from shared.constants import COLLECTION_FACTS
from shared.queue import push_result

from ..agents.tools import complement_tool

log = logging.getLogger(__name__)

FACTS_K = 15            # how many candidate facts to pull
FACTS_TOP = 5           # how many to actually pass to the prompt


def _cart_context(products: list[dict]) -> str:
    """Compact text for embedding — drives customer-facts retrieval."""
    parts = [
        f"{p.get('name', '')} ({p.get('subcategory', '')})"
        for p in products
    ]
    return "shopping cart: " + "; ".join(parts)


def _retrieve_customer_facts(
    customer_id: str,
    cart_products: list[dict],
    bedrock,
    vectors,
) -> list[str]:
    """Returns up to FACTS_TOP fact texts ranked by ACE (recency × similarity).
    Empty list on any failure or for new customers with no facts."""
    if not cart_products:
        return []
    try:
        query_vec = bedrock.embed(_cart_context(cart_products))
        raw_facts = vectors.search(
            COLLECTION_FACTS, query_vec, k=FACTS_K, filter_customer=customer_id,
        )
    except Exception as e:
        log.warning("complement fact retrieval failed: %s", e)
        return []

    ranked, _conflicts = rank_facts(raw_facts)
    return [f["text"] for f in ranked[:FACTS_TOP] if f.get("text")]


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

    # Resolve cart for fact-context embedding (and pass through the count to
    # the tool's own batch_get implicitly — tool also fetches; cost is <1ms).
    cart_products = dynamo.batch_get_recommender_products(cart_items) if cart_items else []

    t_facts = time.time()
    facts_texts = _retrieve_customer_facts(
        customer_id, cart_products, bedrock, vectors,
    )
    facts_ms = (time.time() - t_facts) * 1000
    tracer.log(
        job_id, "complement", "facts_retrieved",
        {"customer_id": customer_id, "k": FACTS_K, "top": FACTS_TOP},
        {"facts_count": len(facts_texts), "facts_preview": facts_texts[:2]},
        facts_ms, "ok",
    )

    t0 = time.time()
    result = complement_tool.generate_complement_recommendation(
        customer_id=customer_id,
        cart_item_ids=cart_items,
        bedrock=bedrock,
        dynamo=dynamo,
        customer_facts=facts_texts,
        limit=limit,
    )
    duration_ms = (time.time() - t0) * 1000

    tracer.log(
        job_id, "complement", "generate_complement",
        {"cart_size": len(cart_items), "limit": limit, "facts_used": len(facts_texts)},
        {
            "recommendations": len(result["recommendations"]),
            "candidates_considered": result["candidates_considered"],
            "used_llm": result["used_llm"],
        },
        duration_ms, "ok",
    )

    result["facts_used"] = len(facts_texts)
    push_result(redis_client, job_id, json.dumps({**result, "job_id": job_id}))
    tracer.log(
        job_id, "supervisor", "end_complement",
        {}, {"recs_returned": len(result["recommendations"])},
        0.0, "ok",
    )
    log.info(
        "complement result pushed for job %s (facts=%d, recs=%d, llm=%s)",
        job_id, len(facts_texts), len(result["recommendations"]), result["used_llm"],
    )
