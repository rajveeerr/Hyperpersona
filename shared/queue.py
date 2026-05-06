"""Redis-backed job queue helper.

In Phase 10 the queue swaps to SQS; this module is the only place callers
talk to Redis, so the swap is mechanical.
"""

import redis as _redis

from .constants import QUEUE_PENDING


def make_redis(url: str) -> _redis.Redis:
    return _redis.from_url(url, decode_responses=True)


def push_job(client: _redis.Redis, payload: str) -> None:
    """LPUSH a job JSON payload onto the pending queue."""
    client.lpush(QUEUE_PENDING, payload)


def push_jobs(client: _redis.Redis, payloads: list[str]) -> None:
    """LPUSH many jobs in one round-trip. Pop order matches submission order."""
    if not payloads:
        return
    client.lpush(QUEUE_PENDING, *payloads)


def pop_job(client: _redis.Redis, timeout: int = 0) -> str | None:
    """BRPOP a job JSON payload (blocking). Returns None on timeout."""
    result = client.brpop(QUEUE_PENDING, timeout=timeout)
    return result[1] if result else None


# --- Per-job result channel -----------------------------------------------
# Pattern: worker LPUSHes onto result:{job_id}, server BRPOPs it. The list
# also gets a TTL so abandoned results don't leak forever.

def _result_key(job_id: str) -> str:
    return f"result:{job_id}"


def push_result(
    client: _redis.Redis,
    job_id: str,
    payload: str,
    ttl_seconds: int = 60,
) -> None:
    """Push a job result onto the per-job result list."""
    key = _result_key(job_id)
    client.lpush(key, payload)
    client.expire(key, ttl_seconds)


def pop_result(
    client: _redis.Redis,
    job_id: str,
    timeout: int = 30,
) -> str | None:
    """BRPOP a result for a job. Returns None on timeout."""
    result = client.brpop(_result_key(job_id), timeout=timeout)
    return result[1] if result else None


async def pop_result_async(
    client_async,
    job_id: str,
    timeout: int = 30,
) -> str | None:
    """Async BRPOP — for use inside FastAPI async handlers. Releases the
    event loop while waiting, so one process can multiplex many waits
    instead of pinning one thread per in-flight request.

    `client_async` must be a redis.asyncio client (see server/src/deps.py).
    """
    result = await client_async.brpop(_result_key(job_id), timeout=timeout)
    return result[1] if result else None
