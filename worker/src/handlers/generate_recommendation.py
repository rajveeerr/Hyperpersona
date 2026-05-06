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
from ..agents.tools._product_reco_helpers import build_personalization_reason

log = logging.getLogger(__name__)


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
    result["personalization_reason"] = build_personalization_reason(ranked_facts)
    result["job_id"] = job_id

    push_result(redis_client, job_id, json.dumps(result))
    log.info(
        "recommendation result pushed for job %s (products=%d, facts=%d)",
        job_id, len(picker_out["products"]), len(ranked_facts),
    )
