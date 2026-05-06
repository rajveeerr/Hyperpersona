"""Job queue + per-job result channel.

Two distinct primitives, two backend stories:

  - JobQueue: durable incoming work for the worker. Pluggable —
    QUEUE_MODE=redis (default) or QUEUE_MODE=sqs. Use make_job_queue(...).

  - Result channel: per-job, server-waits-for-worker. Always Redis,
    because BRPOP semantics + 30s lifetime are exactly what's needed
    and SQS isn't a great fit for "wait by id" lookups. The push_result/
    pop_result/pop_result_async helpers below are unchanged.

The split is deliberate: SQS gives the job queue durability, replay,
and at-least-once delivery (good for production); Redis stays for the
ephemeral request-response sync where its semantics shine.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable, Protocol

import redis as _redis

from .constants import QUEUE_PENDING

log = logging.getLogger(__name__)


# ============================================================================
# JobQueue — pluggable
# ============================================================================


@dataclass
class PoppedJob:
    """A job pulled off the queue.

    `payload` is the JSON-serialized Job. `ack()` finalizes the dequeue:
    no-op for Redis (BRPOP already removed it), delete_message for SQS
    (the message is in-flight until ack'd; on no-ack the visibility
    timeout fires and SQS redelivers).
    """
    payload: str
    ack: Callable[[], None]


class JobQueue(Protocol):
    def push_one(self, payload: str) -> None: ...
    def push_many(self, payloads: list[str]) -> None: ...
    def pop(self, timeout: int = 20) -> PoppedJob | None: ...
    def depth(self) -> int: ...


# --- Redis impl -------------------------------------------------------------


class RedisJobQueue:
    """LPUSH/BRPOP-based queue. Atomic pop (no in-flight state)."""

    def __init__(self, redis_client: _redis.Redis, key: str = QUEUE_PENDING) -> None:
        self.client = redis_client
        self.key = key

    def push_one(self, payload: str) -> None:
        self.client.lpush(self.key, payload)

    def push_many(self, payloads: list[str]) -> None:
        if not payloads:
            return
        self.client.lpush(self.key, *payloads)

    def pop(self, timeout: int = 20) -> PoppedJob | None:
        # BRPOP with timeout=0 means block forever; our callers default to 0.
        # Accept either convention.
        result = self.client.brpop(self.key, timeout=timeout)
        if result is None:
            return None
        # No ack needed — BRPOP atomically removed it.
        return PoppedJob(payload=result[1], ack=lambda: None)

    def depth(self) -> int:
        return int(self.client.llen(self.key))


# --- SQS impl ---------------------------------------------------------------


class SqsJobQueue:
    """SQS-backed queue. Long-poll receive, explicit delete on ack.

    Visibility timeout should exceed the worst-case job duration so
    in-progress jobs aren't redelivered. We default to 90s (covers
    Strands ingest at ~17s + the 3-attempt retry-with-backoff at ~7s
    cumulative delays).
    """

    BATCH_LIMIT = 10  # SQS hard cap on send_message_batch

    def __init__(self, sqs_client, queue_url: str) -> None:
        self.sqs = sqs_client
        self.queue_url = queue_url

    def push_one(self, payload: str) -> None:
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=payload)

    def push_many(self, payloads: list[str]) -> None:
        if not payloads:
            return
        # SQS batches max 10 entries per call.
        for i in range(0, len(payloads), self.BATCH_LIMIT):
            chunk = payloads[i:i + self.BATCH_LIMIT]
            entries = [
                {"Id": str(idx), "MessageBody": body}
                for idx, body in enumerate(chunk)
            ]
            resp = self.sqs.send_message_batch(QueueUrl=self.queue_url, Entries=entries)
            failed = resp.get("Failed", []) or []
            if failed:
                # Don't silently lose messages — surface so the retry/idempotency
                # layer above us decides what to do.
                raise RuntimeError(f"sqs.send_message_batch had failures: {failed}")

    def pop(self, timeout: int = 20) -> PoppedJob | None:
        # SQS long-poll WaitTimeSeconds tops out at 20.
        wait = max(1, min(timeout if timeout > 0 else 20, 20))
        resp = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait,
        )
        msgs = resp.get("Messages") or []
        if not msgs:
            return None
        msg = msgs[0]
        receipt = msg["ReceiptHandle"]
        queue_url = self.queue_url
        sqs = self.sqs

        def _ack() -> None:
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)

        return PoppedJob(payload=msg["Body"], ack=_ack)

    def depth(self) -> int:
        # ApproximateNumberOfMessages — eventually consistent but close enough
        # for backpressure decisions.
        attrs = self.sqs.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        return int(attrs.get("Attributes", {}).get("ApproximateNumberOfMessages", "0"))


# --- Factory ----------------------------------------------------------------


def make_job_queue(
    mode: str,
    *,
    redis_client: _redis.Redis | None = None,
    sqs_queue_url: str = "",
    region: str = "us-east-1",
) -> JobQueue:
    if mode == "redis":
        if redis_client is None:
            raise ValueError("QUEUE_MODE=redis requires a redis_client")
        log.info("JobQueue: redis (key=%s)", QUEUE_PENDING)
        return RedisJobQueue(redis_client)
    if mode == "sqs":
        if not sqs_queue_url:
            raise ValueError("QUEUE_MODE=sqs requires SQS_QUEUE_URL to be set")
        import boto3
        sqs = boto3.client("sqs", region_name=region)
        log.info("JobQueue: sqs (url=%s)", sqs_queue_url)
        return SqsJobQueue(sqs, sqs_queue_url)
    raise ValueError(f"Unknown QUEUE_MODE: {mode!r} (expected 'redis' or 'sqs')")


# ============================================================================
# Redis client + per-job result channel — unchanged
# ============================================================================


def make_redis(url: str) -> _redis.Redis:
    return _redis.from_url(url, decode_responses=True)


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
    """Async BRPOP — for use inside FastAPI async handlers."""
    result = await client_async.brpop(_result_key(job_id), timeout=timeout)
    return result[1] if result else None


# ============================================================================
# Backwards-compat shims — let unmigrated callers keep working
# ============================================================================
# These match the old free-function signatures. Callers that already use
# JobQueue methods don't need them. We delete them once everything migrates.


def push_job(client: _redis.Redis, payload: str) -> None:
    """Deprecated: use job_queue.push_one(payload). Routes through Redis only."""
    RedisJobQueue(client).push_one(payload)


def push_jobs(client: _redis.Redis, payloads: list[str]) -> None:
    """Deprecated: use job_queue.push_many(payloads). Routes through Redis only."""
    RedisJobQueue(client).push_many(payloads)


def pop_job(client: _redis.Redis, timeout: int = 0) -> str | None:
    """Deprecated: use job_queue.pop(timeout). Routes through Redis only."""
    popped = RedisJobQueue(client).pop(timeout=timeout)
    return popped.payload if popped else None
