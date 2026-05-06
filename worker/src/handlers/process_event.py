"""Tiered event handler.

Routes events by signal value:
  - HIGH-SIGNAL (purchase, add_to_cart, search, return)
      Full supervisor pipeline: privacy gate → analyzer → vector upserts.
      ~3-5 Bedrock calls per event.
  - LOW-SIGNAL (page_view, scroll, hover, anything else)
      Cheap path: just mark status=processed_cheap, increment a Redis counter.
      When the counter hits SESSION_FLUSH_THRESHOLD, enqueue a single
      summarize_session job that rolls up all cheap events into one summary
      embedding. Net effect: N low-signal events become ~1 Bedrock call.
"""

import json
import logging

from shared.constants import (
    EVENT_STATUS_AGGREGATED,
    EVENT_STATUS_CHEAP,
    EVENT_STATUS_PROCESSED,
    HIGH_SIGNAL_EVENT_TYPES,
    NOISE_EVENT_TYPES,
)
from shared.schemas import Job

log = logging.getLogger(__name__)


def handle(job: dict, ctx: dict) -> None:
    payload = job["payload"]
    customer_id = payload["customer_id"]
    event_id = payload["event_id"]

    dynamo = ctx["dynamo"]
    redis_client = ctx["redis"]
    settings = ctx["settings"]

    event = dynamo.get_event(customer_id, event_id)
    if not event:
        raise ValueError(f"event {event_id} not found in DynamoDB")

    event_type = event.get("event_type", "")

    # Noise gate (applies in BOTH "full" and "tiered" modes). Events the
    # frontend spec explicitly says NOT to track (page_view, UI-state pings)
    # produce trivial Claude facts like "the customer viewed a page" that
    # pollute customer-facts and dilute KNN ranking. Mark them aggregated
    # immediately and skip Bedrock work entirely. See NOISE_EVENT_TYPES in
    # shared/constants.py for the full list and rationale.
    if event_type in NOISE_EVENT_TYPES:
        log.info(
            "noise event (skipped)",
            extra={"event_type": event_type, "customer_id": customer_id, "event_id": event_id},
        )
        dynamo.update_event_status(customer_id, event_id, EVENT_STATUS_AGGREGATED)
        return

    # In "full" mode (default), every event runs the supervisor regardless of
    # type — maximum accuracy, no signal lost. In "tiered" mode, low-signal
    # events skip the supervisor and get rolled up by summarize_session.
    if settings.event_processing_mode == "tiered" and event_type not in HIGH_SIGNAL_EVENT_TYPES:
        _handle_low_signal(job, ctx, event, redis_client, settings, dynamo)
    else:
        _handle_high_signal(job, ctx, event)


def _handle_high_signal(job: dict, ctx: dict, event: dict) -> None:
    customer_id = event["customer_id"]
    event_id = event["event_id"]
    dynamo = ctx["dynamo"]
    supervisor = ctx["supervisor"]

    log.info(
        "high-signal event",
        extra={"event_type": event["event_type"], "customer_id": customer_id, "event_id": event_id},
    )
    dynamo.update_event_status(customer_id, event_id, "processing")
    result = supervisor.run_process_event(job["job_id"], event)
    dynamo.update_event_status(customer_id, event_id, EVENT_STATUS_PROCESSED)
    log.info(
        "high-signal done",
        extra={"event_id": event_id, "status": result.get("status")},
    )


def _handle_low_signal(job: dict, ctx: dict, event: dict, redis_client, settings, dynamo) -> None:
    customer_id = event["customer_id"]
    event_id = event["event_id"]
    tracer = ctx["tracer"]

    log.info(
        "low-signal event (cheap-store)",
        extra={"event_type": event["event_type"], "customer_id": customer_id, "event_id": event_id},
    )
    dynamo.update_event_status(customer_id, event_id, EVENT_STATUS_CHEAP)

    counter_key = f"session:{customer_id}:cheap_count"
    new_count = int(redis_client.incr(counter_key))
    redis_client.expire(counter_key, 24 * 3600)

    tracer.log(
        job["job_id"], "router", "cheap_store",
        {"customer_id": customer_id, "event_type": event["event_type"]},
        {"counter": new_count, "threshold": settings.session_flush_threshold},
        0.0, "ok",
    )

    if new_count >= settings.session_flush_threshold:
        # Reset counter atomically before enqueueing — avoids re-firing if
        # multiple cheap events land in quick succession.
        redis_client.delete(counter_key)
        summary_job = Job(
            job_type="summarize_session",
            payload={"customer_id": customer_id},
        )
        dynamo.put_job(summary_job.model_dump())
        ctx["queue"].push_one(summary_job.model_dump_json())
        log.info(
            "summarize_session enqueued",
            extra={"customer_id": customer_id, "counter_at_trigger": new_count},
        )
