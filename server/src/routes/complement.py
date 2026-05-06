"""Complementary-products endpoint.

GET /recommend/complement?cart_items=p1,p2,p3
  → ranked list of products typically bought WITH the cart contents.

Async handler with the same BRPOP-on-redis_async pattern as /recommend,
so the server doesn't pin a thread per in-flight request.

Caching: cache_key = sha256(customer_id + sorted(cart_items) + limit).
Same customer + same cart contents → 5-min cached result. Sorting
cart_items first means [a,b,c] and [c,b,a] hit the same cache key.

Auth: customer_id resolved from JWT (Depends(current_customer_id)).
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

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
# 60s budget — same reasoning as /recommend: Opus is slower than Sonnet.
RESULT_TIMEOUT_SECONDS = 60
MAX_CART_SIZE = 20             # protect against runaway clients


def _cache_key(customer_id: str, cart_items: list[str], limit: int) -> str:
    # Sorted so cart order doesn't matter for cache hits
    payload = "|".join(sorted(cart_items)) + f"|{limit}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"complement:{customer_id}:{h}"


@router.get("/recommend/complement")
async def recommend_complement(
    cart_items: str = Query(
        ...,
        min_length=1,
        description="Comma-separated product_ids in the cart",
    ),
    limit: int = Query(5, ge=1, le=10),
    customer_id: str = Depends(current_customer_id),
) -> dict:
    item_ids = [p.strip() for p in cart_items.split(",") if p.strip()]
    if not item_ids:
        raise HTTPException(status_code=400, detail="cart_items must be non-empty")
    if len(item_ids) > MAX_CART_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"cart_items exceeds max of {MAX_CART_SIZE}",
        )

    # Cache check — fast path for repeat queries
    cache_key = _cache_key(customer_id, item_ids, limit)
    cached = _redis.get(cache_key)
    if cached:
        log.info("complement cache hit: %s", cache_key)
        result = json.loads(cached)
        result["cached"] = True
        return result

    job = Job(
        job_type="generate_related_recommendation",
        payload={
            "mode": "complement",
            "customer_id": customer_id,
            "cart_items": item_ids,
            "limit": limit,
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
            detail=f"complement recommendation timed out after {RESULT_TIMEOUT_SECONDS}s",
        )

    result = json.loads(payload)
    result["cached"] = False
    _redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    return result
