"""Personalized recommendation endpoint.

Cache check → enqueue generate_recommendation job → wait for the worker
to push a result → cache it → return.

This is an async handler so a single uvicorn process can multiplex many
in-flight /recommend requests on the event loop instead of pinning one
thread per request for up to 30s on the BRPOP. Throughput cap goes from
~40 concurrent (sync handler thread pool) to thousands.

The sync ops (cache check, put_job, push_job, setex) are sub-millisecond
on local Redis/DDB so blocking the loop briefly is fine. Only the long
BRPOP needs to be async.
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.queue import pop_result_async, push_job
from shared.schemas import Job

from ..deps import dynamo as _dynamo
from ..deps import redis_async as _redis_async
from ..deps import redis_client as _redis
from ..middleware.auth import current_customer_id


log = logging.getLogger(__name__)
router = APIRouter()

CACHE_TTL_SECONDS = 300
RESULT_TIMEOUT_SECONDS = 30


def _cache_key(customer_id: str, context: str) -> str:
    h = hashlib.sha256(context.encode("utf-8")).hexdigest()[:16]
    return f"offer:{customer_id}:{h}"


@router.get("/recommend")
async def recommend(
    context: str = Query(..., min_length=1),
    customer_id: str = Depends(current_customer_id),
) -> dict:
    cache_key = _cache_key(customer_id, context)

    cached = _redis.get(cache_key)
    if cached:
        log.info("recommend cache hit: %s", cache_key)
        result = json.loads(cached)
        result["cached"] = True
        return result

    job = Job(
        job_type="generate_recommendation",
        payload={"customer_id": customer_id, "context": context},
    )
    _dynamo.put_job(job.model_dump())
    push_job(_redis, job.model_dump_json())

    # Long wait — async so the event loop stays free for other requests.
    payload = await pop_result_async(
        _redis_async, job.job_id, timeout=RESULT_TIMEOUT_SECONDS,
    )
    if payload is None:
        raise HTTPException(
            status_code=504,
            detail=f"recommendation timed out after {RESULT_TIMEOUT_SECONDS}s",
        )

    result = json.loads(payload)
    result["cached"] = False
    _redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    return result
