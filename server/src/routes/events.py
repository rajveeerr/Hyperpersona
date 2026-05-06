"""Event ingestion — singular and batch.

Both endpoints share `_ingest_events`, which:
  - dedups within the batch by client_event_id (first occurrence wins)
  - reads consent once for the auth'd customer (every event in a single
    request belongs to the same JWT-resolved customer_id)
  - per-event scope check: accepts if the intersection of the event's
    declared `consent_scope` and the customer's granted scopes is
    non-empty. The stored event carries that intersection so downstream
    consumers know what they're allowed to do with each row. Worker-side
    gates (privacy_tool.py) still independently require `personalization`
    before using events for ranking.
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
from ..deps import job_queue as _queue
from ..deps import redis_client as _redis
from ..middleware.auth import current_customer_id


router = APIRouter()


def _claim_rate_budget(customer_id: str, want: int) -> int:
    """Atomically reserve up to `want` slots from the customer's per-minute
    rate budget. Returns how many were actually granted (in [0, want]).

    Behavior:
      - one INCRBY for the whole batch instead of N incr/decr round-trips,
      - if the new total overshoots the limit, decrement back the overflow
        and grant only the slack that was available,
      - fixed window keyed on `int(time.time() // 60)` — sliding would be
        more accurate but not needed at this scale.
    """
    if want <= 0:
        return 0
    limit = settings.max_events_per_customer_per_min
    bucket = f"rate:cust:{customer_id}:{int(time.time() // 60)}"
    new_count = _redis.incrby(bucket, want)
    # First write into the bucket sets its TTL — 65s window guards against
    # clock skew at minute boundaries.
    if new_count == want:
        _redis.expire(bucket, 65)
    if new_count <= limit:
        return want
    overflow = min(want, new_count - limit)
    _redis.decrby(bucket, overflow)
    granted = max(0, want - overflow)
    return granted


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

    granted_scopes: set[str] = set(consent.get("scopes") or set()) if consent else set()

    result_by_id: dict[str, IngestEventResult] = {}

    # Pass 1 — apply consent gate up front so we know how many events are
    # actually eligible to consume rate budget. Events that fail the gate
    # are recorded immediately; eligible ones move on to the rate check.
    eligible: list[tuple[IngestEventRequest, set[str]]] = []
    for r in unique:
        if not consent:
            result_by_id[r.client_event_id] = IngestEventResult(
                client_event_id=r.client_event_id,
                status="rejected",
                reason="no_consent_record",
            )
            continue

        # Per-event scope check. The event declares which scopes it would use
        # (analytics for recording/funnels, personalization for ranking, etc.);
        # we accept if the customer has granted at least one. This decouples
        # ingest (analytics) from recommendation use (personalization, gated
        # separately by privacy_tool.py at the worker layer).
        #
        # An event with no declared scope falls back to {"analytics"} — every
        # event is at minimum an analytics signal. The stored consent_scope
        # is the intersection, so the worker knows what it's allowed to do
        # with each row even if the customer later revokes a scope.
        requested = set(r.consent_scope or set()) or {"analytics"}
        effective = requested & granted_scopes
        if not effective:
            missing = sorted(requested - granted_scopes)
            result_by_id[r.client_event_id] = IngestEventResult(
                client_event_id=r.client_event_id,
                status="rejected",
                reason=f"missing_scope:{','.join(missing)}",
            )
            continue

        eligible.append((r, effective))

    # Pass 2 — claim the customer's rate-limit budget in one Redis op for
    # the whole eligible set. Granted prefix is accepted, the rest reject
    # with `customer_rate_limit`. Counted only against post-consent events
    # so denied/ungated customers don't burn another's budget.
    granted = _claim_rate_budget(customer_id, len(eligible)) if eligible else 0
    accepted_events: list[dict] = []
    accepted_jobs: list[dict] = []
    accepted_payloads: list[str] = []

    if eligible:
        retention_days = int(consent.get("data_retention_days", 90))
        expires_at = now_epoch + retention_days * 86400
        for idx, (r, effective) in enumerate(eligible):
            if idx >= granted:
                result_by_id[r.client_event_id] = IngestEventResult(
                    client_event_id=r.client_event_id,
                    status="rejected",
                    reason="customer_rate_limit",
                )
                continue
            event = CustomerEvent(
                customer_id=customer_id,
                event_id=r.client_event_id,
                event_type=r.event_type,
                payload=r.payload,
                consent_scope=effective,
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
        # Filter out jobs that already finished — re-enqueueing them would
        # create duplicate work on the queue (matters more under SQS, since
        # each duplicate is a real network message vs Redis LPUSH dups). DDB
        # is the source of truth for "this job already ran".
        existing_jobs = _dynamo.batch_get_jobs([job["job_id"] for job in accepted_jobs])
        terminal_ids = {
            j["job_id"]
            for j in existing_jobs
            if j.get("status") in ("completed", "failed")
        }
        jobs_to_enqueue = [j for j in accepted_jobs if j["job_id"] not in terminal_ids]
        payloads_to_enqueue = [
            payload for job, payload in zip(accepted_jobs, accepted_payloads)
            if job["job_id"] not in terminal_ids
        ]
        if jobs_to_enqueue:
            _dynamo.batch_put_jobs(jobs_to_enqueue)
            _queue.push_many(payloads_to_enqueue)

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
