"""Handle generate_recommendation jobs.

Delegates to RecommendSupervisor (manual or strands), then writes the
result to result:{job_id} in Redis so the waiting server can pick it up.
"""

import json
import logging

from shared.queue import push_result

log = logging.getLogger(__name__)


def handle(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    context = payload["context"]

    supervisor = ctx["recommend_supervisor"]
    redis_client = ctx["redis"]

    result = supervisor.run_recommend(job_id, customer_id, context)
    result["job_id"] = job_id

    push_result(redis_client, job_id, json.dumps(result))
    log.info("recommendation result pushed for job %s", job_id)
