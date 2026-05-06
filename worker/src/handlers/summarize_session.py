"""Roll up cheap-stored low-signal events into one session summary.

Reads all events for the customer with status=processed_cheap. Asks Claude
to write a one-sentence narrative summary (much better embedding fodder
than concatenated event lines), embeds it once, stores it in the
session-summaries collection, and marks the source events as 'aggregated'.

Cost: 1 generate + 1 embed per summary, vs 1 embed in the previous concat
version. Still ~6× cheaper than running the full supervisor per event.

Mock-mode behavior: MockBedrockClient.generate returns a stub starting with
"[mock]". We detect that and fall back to the concat format so the demo
output stays readable. Real Bedrock produces a real narrative.

Idempotency: summary doc_id is sha256(sorted event_ids), so a retry
overwrites the same row. Status updates are also idempotent.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone

from shared.constants import (
    COLLECTION_SESSIONS,
    EVENT_STATUS_AGGREGATED,
    EVENT_STATUS_CHEAP,
)

log = logging.getLogger(__name__)


_NARRATIVE_SYSTEM = (
    "You write one-sentence narrative summaries of customer browsing activity. "
    "Use only the events provided. Focus on what the customer was exploring or "
    "considering, not the verbatim URLs. Keep it under 30 words."
)

_NARRATIVE_PROMPT = (
    "Summarize this customer's recent low-signal activity in ONE concise sentence.\n\n"
    "Activity:\n{events}"
)


def _raw_event_lines(events: list[dict]) -> str:
    bits: list[str] = []
    for e in events:
        evt_type = e.get("event_type", "unknown")
        payload = e.get("payload") or {}
        payload_str = ", ".join(f"{k}={v}" for k, v in payload.items())
        bits.append(f"- {evt_type}({payload_str})" if payload_str else f"- {evt_type}")
    return "\n".join(bits)


def _concat_fallback(raw_lines: str) -> str:
    return "Recent low-signal activity: " + "; ".join(
        line.lstrip("- ") for line in raw_lines.split("\n")
    )


def _looks_like_mock(text: str) -> bool:
    return text.strip().startswith("[mock]")


def _build_summary_text(events: list[dict], bedrock) -> tuple[str, bool]:
    """Returns (text, used_narrative). used_narrative=True means a real
    Bedrock generate succeeded; False means we fell back to concat."""
    raw_lines = _raw_event_lines(events)
    try:
        narrative = bedrock.generate(
            prompt=_NARRATIVE_PROMPT.format(events=raw_lines),
            system=_NARRATIVE_SYSTEM,
            max_tokens=100,
        ).strip()
        if narrative and not _looks_like_mock(narrative):
            return narrative, True
    except Exception:
        log.warning("summary narrative generate failed; falling back", exc_info=True)
    return _concat_fallback(raw_lines), False


def handle(job: dict, ctx: dict) -> None:
    customer_id = job["payload"]["customer_id"]

    dynamo = ctx["dynamo"]
    bedrock = ctx["bedrock"]
    vectors = ctx["vectors"]
    tracer = ctx["tracer"]
    job_id = job["job_id"]

    t0 = time.time()
    all_events = dynamo.query_events(customer_id)
    pending = [e for e in all_events if e.get("status") == EVENT_STATUS_CHEAP]

    if not pending:
        log.info("summarize_session: no pending events", extra={"customer_id": customer_id})
        tracer.log(
            job_id, "summarizer", "noop",
            {"customer_id": customer_id}, {"reason": "no_pending"},
            (time.time() - t0) * 1000, "ok",
        )
        return

    summary_text, used_narrative = _build_summary_text(pending, bedrock)
    vec = bedrock.embed(summary_text)

    event_ids = sorted(str(e["event_id"]) for e in pending)
    digest = hashlib.sha256(":".join(event_ids).encode("utf-8")).hexdigest()[:16]
    summary_id = f"summary_{customer_id}_{digest}"

    vectors.upsert(
        COLLECTION_SESSIONS,
        summary_id,
        vec,
        {
            "customer_id": customer_id,
            "text": summary_text,
            "event_count": len(pending),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Mark events as aggregated so the next summarize doesn't pick them up again
    for e in pending:
        dynamo.update_event_status(customer_id, e["event_id"], EVENT_STATUS_AGGREGATED)

    duration_ms = (time.time() - t0) * 1000
    tracer.log(
        job_id, "summarizer", "session_summary",
        {"customer_id": customer_id, "event_count": len(pending)},
        {
            "summary_id": summary_id,
            "summary_len": len(summary_text),
            "used_narrative": used_narrative,
        },
        duration_ms, "ok",
    )
    log.info(
        "summarize_session done",
        extra={
            "customer_id": customer_id,
            "events_aggregated": len(pending),
            "summary_id": summary_id,
            "used_narrative": used_narrative,
            "duration_ms": duration_ms,
        },
    )
