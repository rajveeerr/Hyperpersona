"""Event ingestion — singular and batch.

Both endpoints share `_ingest_events`, which:
  - dedups within the batch by client_event_id (first occurrence wins)
  - reads consent once for the auth'd customer (every event in a single
    request belongs to the same JWT-resolved customer_id)
  - rejects events for ungated customers with status="rejected"
  - bulk-writes accepted events + jobs to DynamoDB (BatchWriteItem)
  - pipelined LPUSH of all jobs onto the worker queue

Idempotency:
  - event_id = client_event_id (frontend-supplied UUID)
  - job_id   = f"evt_{client_event_id}"  (deterministic from event)
  - Retries overwrite the same DDB rows on PK+SK collision; deterministic
    vector doc_ids in the analyzer keep OpenSearch idempotent too.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from shared.constants import QUEUE_PENDING
from shared.queue import push_jobs
from shared.schemas import (
    CustomerEvent,
    IngestBatchRequest,
    IngestBatchResponse,
    IngestEventRequest,
    IngestEventResult,
    Job,
)

from ..config import settings
from ..deps import dynamo as _dynamo
from ..deps import redis_client as _redis
from ..middleware.auth import current_customer_id


router = APIRouter()


def _rate_limited_for_customer(customer_id: str) -> bool:
    """Increment the customer's per-minute counter. Returns True if over limit
    (in which case the increment is rolled back so we don't count rejections).
    Fixed window — sliding would be more accurate but isn't needed at this scale.
    """
    bucket = f"rate:cust:{customer_id}:{int(time.time() // 60)}"
    count = _redis.incr(bucket)
    if count == 1:
        _redis.expire(bucket, 65)
    if count > settings.max_events_per_customer_per_min:
        _redis.decr(bucket)
        return True
    return False


def _ingest_events(
    customer_id: str,
    reqs: list[IngestEventRequest],
) -> IngestBatchResponse:
    # Backpressure: refuse new work when the worker queue is too deep.
    # Whole-request rejection (429) — not partial — because the system can't
    # accept anything new until it drains.
    queue_depth = _redis.llen(QUEUE_PENDING)
    if queue_depth > settings.max_queue_depth:
        raise HTTPException(
            status_code=429,
            detail=(
                f"queue overloaded ({queue_depth} pending, "
                f"limit {settings.max_queue_depth}) — try again shortly"
            ),
        )


    # Dedup within the batch — first occurrence wins.
    by_id: dict[str, IngestEventRequest] = {}
    for r in reqs:
        by_id.setdefault(r.client_event_id, r)
    unique = list(by_id.values())

    # All events in a single request belong to the auth'd customer — one
    # consent read covers the whole batch.
    consent = _dynamo.get_consent(customer_id)

    now_epoch = int(datetime.now(timezone.utc).timestamp())

    accepted_events: list[dict] = []
    accepted_jobs: list[dict] = []
    accepted_payloads: list[str] = []
    result_by_id: dict[str, IngestEventResult] = {}

    for r in unique:
        if not consent:
            result_by_id[r.client_event_id] = IngestEventResult(
                client_event_id=r.client_event_id,
                status="rejected",
                reason="no_consent_record",
            )
            continue
        if "personalization" not in (consent.get("scopes") or set()):
            result_by_id[r.client_event_id] = IngestEventResult(
                client_event_id=r.client_event_id,
                status="rejected",
                reason="missing_personalization_scope",
            )
            continue

        # Per-customer rate limit. Counted only against accepted-after-consent
        # events so denied/ungated customers don't burn another's budget.
        # All events in one request belong to the same auth'd customer.
        if _rate_limited_for_customer(customer_id):
            result_by_id[r.client_event_id] = IngestEventResult(
                client_event_id=r.client_event_id,
                status="rejected",
                reason="customer_rate_limit",
            )
            continue

        retention_days = int(consent.get("data_retention_days", 90))
        expires_at = now_epoch + retention_days * 86400

        event = CustomerEvent(
            customer_id=customer_id,
            event_id=r.client_event_id,
            event_type=r.event_type,
            payload=r.payload,
            consent_scope=r.consent_scope,
            expires_at=expires_at,
        )
        job = Job(
            job_id=f"evt_{r.client_event_id}",
            job_type="process_event",
            payload={
                "event_id": event.event_id,
                "customer_id": event.customer_id,
            },
        )
        accepted_events.append(event.model_dump())
        accepted_jobs.append(job.model_dump())
        accepted_payloads.append(job.model_dump_json())
        result_by_id[r.client_event_id] = IngestEventResult(
            client_event_id=r.client_event_id,
            status="queued",
            event_id=event.event_id,
            job_id=job.job_id,
        )

    if accepted_events:
        _dynamo.batch_put_events(accepted_events)
        _dynamo.batch_put_jobs(accepted_jobs)
        push_jobs(_redis, accepted_payloads)

    # Preserve original submission order; within-batch dups share the same result.
    final_results = [result_by_id[r.client_event_id] for r in reqs]
    accepted = sum(1 for res in final_results if res.status == "queued")
    rejected = len(final_results) - accepted

    return IngestBatchResponse(
        accepted=accepted,
        rejected=rejected,
        results=final_results,
    )


@router.post("/events", status_code=202)
def ingest_event(
    req: IngestEventRequest,
    customer_id: str = Depends(current_customer_id),
) -> dict:
    """Singular endpoint, kept for backwards compat. Routes through the batch path."""
    response = _ingest_events(customer_id, [req])
    result = response.results[0]
    if result.status == "rejected":
        # 429 for rate limit, 403 for everything else (consent failures)
        code = 429 if result.reason == "customer_rate_limit" else 403
        raise HTTPException(status_code=code, detail=result.reason)
    return {
        "event_id": result.event_id,
        "job_id": result.job_id,
        "status": "queued",
    }


@router.post("/events/batch", status_code=200)
def ingest_event_batch(
    req: IngestBatchRequest,
    customer_id: str = Depends(current_customer_id),
) -> IngestBatchResponse:
    return _ingest_events(customer_id, req.events)
