"""Similar-price (substitute) recommendation endpoint.

GET /recommend/similar-price?product_id=<slug>&limit=6&tolerance=0.2
  → ranked list of products in the SAME category at a similar price tier
    as the anchor (iPhone → Pixel/Galaxy). Personalized by customer facts;
    poorly-rated products are dropped.

Same async + cache + queue pattern as /recommend and /recommend/complement:
async BRPOP frees the event loop while the worker generates. Cache key is
namespaced under `pricematch:` and buckets tolerance to integer percent so
0.20 and 0.2001 collapse to one cache entry.

Auth: customer_id resolved from JWT (Depends(current_customer_id)).
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from shared.constants import (
    SIMILAR_PRICE_DEFAULT_LIMIT,
    SIMILAR_PRICE_DEFAULT_TOLERANCE,
)
from shared.queue import pop_result_async
from shared.schemas import Job

from ..deps import dynamo as _dynamo
from ..deps import job_queue as _queue
from ..deps import redis_async as _redis_async
from ..deps import redis_client as _redis
from ..middleware.auth import current_customer_id


log = logging.getLogger(__name__)
router = APIRouter()

CACHE_TTL_SECONDS = 300
# 60s budget — same reasoning as /recommend and /recommend/complement.
RESULT_TIMEOUT_SECONDS = 60


def _cache_key(customer_id: str, product_id: str, tolerance: float, limit: int) -> str:
    # Bucket tolerance by integer percent so 0.20 and 0.2001 collide. The
    # full payload still gets hashed in case product_id has unusual chars.
    tol_bucket = int(round(tolerance * 100))
    payload = f"{product_id}|{tol_bucket}|{limit}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"pricematch:{customer_id}:{h}"


@router.get("/recommend/similar-price")
async def recommend_similar_price(
    product_id: str = Query(..., min_length=1, description="Anchor product slug"),
    limit: int = Query(SIMILAR_PRICE_DEFAULT_LIMIT, ge=1, le=12),
    tolerance: float = Query(
        SIMILAR_PRICE_DEFAULT_TOLERANCE,
        ge=0.05,
        le=0.5,
        description="Price band as a fraction of anchor price (default ±20%)",
    ),
    customer_id: str = Depends(current_customer_id),
) -> dict:
    cache_key = _cache_key(customer_id, product_id, tolerance, limit)
    cached = _redis.get(cache_key)
    if cached:
        log.info("similar-price cache hit: %s", cache_key)
        result = json.loads(cached)
        result["cached"] = True
        return result

    job = Job(
        job_type="generate_related_recommendation",
        payload={
            "mode": "substitute",
            "customer_id": customer_id,
            "product_id": product_id,
            "limit": limit,
            "tolerance": tolerance,
        },
    )
    _dynamo.put_job(job.model_dump())
    _queue.push_one(job.model_dump_json())

    payload = await pop_result_async(
        _redis_async, job.job_id, timeout=RESULT_TIMEOUT_SECONDS,
    )
    if payload is None:
        raise HTTPException(
            status_code=504,
            detail=f"similar-price recommendation timed out after {RESULT_TIMEOUT_SECONDS}s",
        )

    result = json.loads(payload)
    result["cached"] = False
    _redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    return result
