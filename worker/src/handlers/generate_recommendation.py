"""Handle generate_recommendation jobs.

Calls recommender_tool then verifier_tool, writes the final result onto
result:{job_id} in Redis so the waiting server can pick it up. Also
emits trace rows so the same trace inspection works as for process_event.
"""

import json
import logging
import time

from shared.queue import push_result

from ..agents.tools import recommender_tool, verifier_tool

log = logging.getLogger(__name__)


def handle(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    context = payload["context"]

    bedrock = ctx["bedrock"]
    vectors = ctx["vectors"]
    redis_client = ctx["redis"]
    tracer = ctx["tracer"]

    tracer.log(
        job_id, "supervisor", "start_recommend",
        {"customer_id": customer_id, "context_len": len(context)},
        {}, 0.0, "ok",
    )

    # 1. Recommender draft
    t0 = time.time()
    rec = recommender_tool.generate_recommendation(
        customer_id, context, bedrock, vectors,
    )
    tracer.log(
        job_id, "recommender", "generate_recommendation",
        {"customer_id": customer_id, "context_len": len(context)},
        rec, (time.time() - t0) * 1000, "ok",
    )

    # 2. Verifier
    t0 = time.time()
    source_summary = (
        f"context={context}; "
        f"facts_used={rec['facts_used']}; "
        f"behaviors_used={rec['behaviors_used']}; "
        f"summaries_used={rec.get('summaries_used', 0)}"
    )
    verified = verifier_tool.verify_recommendation(
        rec["offer"], source_summary, bedrock,
    )
    tracer.log(
        job_id, "verifier", "verify_recommendation",
        {"draft_len": len(rec.get("offer", ""))},
        verified, (time.time() - t0) * 1000, "ok",
    )

    result = {
        "offer": verified["final_offer"],
        "verifier_status": verified["status"],
        "facts_retrieved": rec.get("facts_retrieved", 0),
        "facts_used": rec["facts_used"],
        "behaviors_used": rec["behaviors_used"],
        "summaries_used": rec.get("summaries_used", 0),
        "conflicts": rec.get("conflicts", []),
        "job_id": job_id,
    }

    push_result(redis_client, job_id, json.dumps(result))
    tracer.log(
        job_id, "supervisor", "end_recommend",
        {}, {"verifier_status": verified["status"]},
        0.0, "ok",
    )
    log.info("recommendation result pushed for job %s", job_id)
