"""Handle generate_recommendation jobs.

Pipeline:
  1. Run the recommend supervisor (manual or strands) → offer text +
     verifier status + ACE-ranked facts.
  2. Pass those ranked facts through the products picker → personalized
     in-stock product cards via blended-KNN over OpenSearch product-catalog.
  3. Build a single 'Because you ...' personalization heading from the
     top Prefers fact (or null for cold start).
  4. Strip the internal `ranked_facts` field, merge picker output, push
     to result:{job_id} for the waiting server.
"""

import json
import logging
import time

from shared.queue import push_result

from ..agents.tools import products_picker_tool

log = logging.getLogger(__name__)


def _build_personalization_reason(ranked_facts: list[dict]) -> str | None:
    """Format the highest-score Prefers fact as a 2nd-person heading.

    Returns None for cold-start (no Prefers facts). The frontend renders a
    fallback heading like 'Recommended for you' in that case.

    Heuristic, not LLM. With real Bedrock we could add a tiny Haiku call to
    rewrite the heading into clean grammar; the heuristic is good enough
    for v1 and ships zero new Bedrock cost.
    """
    prefers = [
        f for f in ranked_facts
        if (f.get("polarity") or 0) >= 0 and f.get("text")
    ]
    if not prefers:
        return None
    # ace_ranking.rank_facts already sorts by combined_score desc, but be
    # explicit so the heading is stable if that ordering convention shifts.
    prefers.sort(key=lambda f: float(f.get("combined_score", 0)), reverse=True)
    top_text = prefers[0]["text"].strip()
    if not top_text:
        return None
    # Lowercase the leading character so "Likes hiking gear" reads as
    # "Because you likes hiking gear" — still grammatically rough but a
    # closer fit than "Because you Likes ...".
    if top_text[0].isupper() and (len(top_text) == 1 or not top_text[1].isupper()):
        top_text = top_text[0].lower() + top_text[1:]
    heading = f"Because you {top_text}"
    return heading[:90]


def handle(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    context = payload["context"]

    supervisor = ctx["recommend_supervisor"]
    redis_client = ctx["redis"]
    bedrock = ctx["bedrock"]
    vectors = ctx["vectors"]
    dynamo = ctx["dynamo"]
    tracer = ctx["tracer"]

    result = supervisor.run_recommend(job_id, customer_id, context)

    # Internal — used to seed the picker + heading; not returned publicly.
    ranked_facts = result.pop("ranked_facts", [])

    t0 = time.time()
    picker_out = products_picker_tool.pick_personalized_products(
        context=context,
        ranked_facts=ranked_facts,
        bedrock=bedrock,
        vectors=vectors,
        dynamo=dynamo,
    )
    duration_ms = (time.time() - t0) * 1000
    tracer.log(
        job_id, "products_picker", "pick_products",
        {"context_len": len(context), "facts_in": len(ranked_facts)},
        {
            "products_returned": len(picker_out["products"]),
            "candidates_considered": picker_out["candidates_considered"],
        },
        duration_ms, "ok",
    )

    result["products"] = picker_out["products"]
    result["candidates_considered"] = picker_out["candidates_considered"]
    result["personalization_reason"] = _build_personalization_reason(ranked_facts)
    result["job_id"] = job_id

    push_result(redis_client, job_id, json.dumps(result))
    log.info(
        "recommendation result pushed for job %s (products=%d, facts=%d)",
        job_id, len(picker_out["products"]), len(ranked_facts),
    )
