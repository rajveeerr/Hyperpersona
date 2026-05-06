"""Job dispatcher with retry-with-backoff.

Reads job_type, routes to the matching handler. On failure, retries up
to MAX_ATTEMPTS times with the delays in RETRY_DELAYS. Final failure
marks the job failed in DynamoDB with the last error.

ctx is a dict of shared singletons (dynamo, bedrock, vectors, tracer,
supervisor, redis, trace_sync) constructed once in main.py and passed
to every handler.

After a successful job, traces are synced via ctx["trace_sync"] in a
background thread. Local SQLite is the source of truth; S3 is best-effort
for cross-restart durability and the AgentCore microVM scenario.
"""

import json
import logging
import threading
import time

from shared.schemas import utc_now_iso

from .handlers import (
    generate_complement_recommendation,
    generate_recommendation,
    process_event,
    summarize_session,
)

log = logging.getLogger(__name__)

HANDLERS = {
    "process_event": process_event.handle,
    "generate_recommendation": generate_recommendation.handle,
    "generate_complement_recommendation": generate_complement_recommendation.handle,
    "summarize_session": summarize_session.handle,
}

# Attempts: 1st immediate, 2nd after 2s, 3rd after 5s
RETRY_DELAYS = [0, 2, 5]


def dispatch(payload: str, ctx: dict) -> None:
    dynamo = ctx["dynamo"]

    job = json.loads(payload)
    job_id = job["job_id"]
    job_type = job["job_type"]

    handler = HANDLERS.get(job_type)
    if handler is None:
        log.error("unknown job_type", extra={"job_type": job_type, "job_id": job_id})
        dynamo.update_job_status(
            job_id,
            "failed",
            completed_at=utc_now_iso(),
            error=f"unknown job_type: {job_type}",
        )
        return

    log.info("dispatch", extra={"job_id": job_id, "job_type": job_type})
    dynamo.update_job_status(job_id, "running")

    last_error: Exception | None = None
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        if delay > 0:
            log.info(
                "retry",
                extra={"job_id": job_id, "attempt": attempt, "delay_s": delay},
            )
            time.sleep(delay)
        try:
            handler(job, ctx)
            dynamo.update_job_status(job_id, "completed", completed_at=utc_now_iso())
            log.info(
                "completed",
                extra={"job_id": job_id, "attempts": attempt},
            )
            _trigger_trace_sync(ctx, job_id)
            return
        except Exception as e:  # noqa: BLE001 — handler errors are caught here
            last_error = e
            log.warning(
                "attempt failed",
                extra={
                    "job_id": job_id,
                    "attempt": attempt,
                    "error_type": type(e).__name__,
                    "error_msg": str(e),
                },
                exc_info=True,
            )

    # All attempts exhausted
    err = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown"
    log.error(
        "failed after retries",
        extra={"job_id": job_id, "attempts": len(RETRY_DELAYS), "error": err},
    )
    dynamo.update_job_status(
        job_id,
        "failed",
        completed_at=utc_now_iso(),
        error=err,
    )
    # Failed jobs still get their traces synced — error rows are useful
    # for post-mortem.
    _trigger_trace_sync(ctx, job_id)


def _trigger_trace_sync(ctx: dict, job_id: str) -> None:
    """Fire trace_sync.sync in a daemon thread so the worker loop never
    blocks on a 100-300ms S3 PUT. NoopTraceSync returns immediately.
    """
    trace_sync = ctx.get("trace_sync")
    tracer = ctx.get("tracer")
    if trace_sync is None or tracer is None:
        return

    def _bg() -> None:
        try:
            trace_sync.sync(tracer.db_path, job_id)
        except Exception:
            log.exception("trace sync failed", extra={"job_id": job_id})

    threading.Thread(target=_bg, daemon=True, name=f"trace-sync-{job_id[:8]}").start()
