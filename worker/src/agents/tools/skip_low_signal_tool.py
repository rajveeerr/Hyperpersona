"""skip_low_signal_tool — store the event vector but skip fact extraction.

The Strands supervisor's orchestrator picks this tool for low-signal events
(page_view, scroll, hover, search-no-click) where the cost of running the
analyzer's Sonnet call exceeds the value of the extracted facts. We still
embed the event so retrieval-time KNN can find it later — we just skip
the LLM-driven fact extraction.

Cost: 1 Titan embed call (~$0.000001) — vs ~$0.0056 for the full analyzer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_BEHAVIOR
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)


def store_event_only(
    customer_id: str,
    event_text: str,
    event_id: str,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
) -> dict:
    """Embed the event and store it in behavior-embeddings — no fact extraction."""
    now = datetime.now(timezone.utc).isoformat()
    vec = bedrock.embed(event_text)
    vectors.upsert(
        COLLECTION_BEHAVIOR,
        event_id,
        vec,
        {
            "customer_id": customer_id,
            "text": event_text,
            "timestamp": now,
            "low_signal": True,
        },
    )
    log.info("skip_low_signal: cust=%s event=%s stored (no facts)",
             customer_id, event_id)
    return {
        "tool": "skip_low_signal",
        "facts_extracted": 0,
        "event_embedded": True,
    }


def make_skip_low_signal_tool(
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
):
    """Strands @tool wrapper. The agent calls this for low-signal events."""
    from strands import tool

    @tool
    def skip_low_signal_tool(
        customer_id: str, event_text: str, event_id: str,
    ) -> dict:
        """Embed and store a low-signal customer event without extracting facts.

        Use this tool when the event_type is page_view, scroll, hover, or a
        search with no follow-on click — events that don't warrant the cost
        of a full Sonnet analyzer pass. The event vector still lands in
        behavior-embeddings so retrieval-time KNN can surface it later.

        Args:
            customer_id: the customer the event belongs to
            event_text: redacted event text (PII already removed)
            event_id: the event's unique ID, used as the doc-id base

        Returns:
            dict with 'facts_extracted' (always 0), 'event_embedded' (True),
            'tool' ('skip_low_signal').
        """
        return store_event_only(customer_id, event_text, event_id, bedrock, vectors)

    return skip_low_signal_tool
