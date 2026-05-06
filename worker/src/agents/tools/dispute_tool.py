"""extract_dispute_reasons_tool — specialized analyzer for returns/complaints.

The Strands supervisor's orchestrator picks this tool for events with
event_type in {return, complaint, refund, support_ticket}. The prompt
is tuned for negative-signal extraction: facts about WHY the customer
is dissatisfied land as polarity=-1, and abstract preferences the
customer has revealed (e.g., "fit matters", "durability matters") land
as polarity=+1 — even though the event is negative.

Critical for downstream: when ACE ranks facts at recommend time, these
strong negative signals about specific products will keep the recommender
from re-suggesting the rejected items. The standard analyzer often misses
this nuance because its prompt is generic.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_BEHAVIOR, COLLECTION_FACTS
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)


_SYSTEM = (
    "You analyze customer DISPUTE events (returns, complaints, refunds, "
    "support tickets). Extract atomic facts ABOUT THE CUSTOMER from the "
    "event. Return a JSON array of {\"text\", \"polarity\"} objects, max 5.\n\n"
    "polarity rules for disputes:\n"
    "  -1  → customer rejected / returned / disliked the specific subject "
    "(most facts will land here for a return event)\n"
    "   1  → an abstract preference the customer has revealed by complaining "
    "(e.g., \"fit matters to this customer\", \"values durability\")\n"
    "   0  → neutral structural info (\"received item on date X\")\n\n"
    "Return ONLY the JSON array — no prose, no markdown.\n\n"
    "Examples:\n"
    "  Event \"return: Nike Pegasus, reason: soles cracked after 2 weeks\"\n"
    '    → [{"text": "rejected Nike Pegasus", "polarity": -1},\n'
    '       {"text": "values shoe durability", "polarity": 1},\n'
    '       {"text": "expects 2+ months of use minimum", "polarity": 1}]\n'
    "  Event \"complaint: shipping took 12 days, missed birthday\"\n"
    '    → [{"text": "rejected slow shipping", "polarity": -1},\n'
    '       {"text": "values fast delivery", "polarity": 1}]'
)

_PROMPT_TEMPLATE = "Dispute event: {text}"


def _parse_facts(generated: str) -> list[dict]:
    try:
        match = re.search(r"\[.*?\]", generated, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback — at least record a generic dispute fact so the recommender
    # knows something went wrong.
    return [{"text": "had a recent dispute with the brand", "polarity": -1}]


def extract_dispute_reasons(
    customer_id: str,
    event_text: str,
    event_id: str,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
) -> dict:
    """Same shape as analyze_behavior but with the dispute-tuned prompt."""
    now = datetime.now(timezone.utc).isoformat()

    # 1. Embed the dispute event itself
    event_vec = bedrock.embed(event_text)
    vectors.upsert(
        COLLECTION_BEHAVIOR,
        event_id,
        event_vec,
        {
            "customer_id": customer_id,
            "text": event_text,
            "timestamp": now,
            "is_dispute": True,
        },
    )

    # 2. Extract dispute-specific facts via Sonnet
    raw = bedrock.generate(
        prompt=_PROMPT_TEMPLATE.format(text=event_text),
        system=_SYSTEM,
    )
    facts = _parse_facts(raw)

    # 3. Embed + store each fact
    fact_entries: list[tuple[str, str, int]] = []
    for fact in facts:
        text = (fact or {}).get("text", "").strip()
        if not text:
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        doc_id = f"{event_id}:{digest}"
        fact_entries.append((doc_id, text, fact.get("polarity", -1)))

    if fact_entries:
        fact_vectors = bedrock.embed_batch([t for (_, t, _) in fact_entries])
        for (doc_id, text, polarity), vec in zip(fact_entries, fact_vectors):
            vectors.upsert(
                COLLECTION_FACTS,
                doc_id,
                vec,
                {
                    "customer_id": customer_id,
                    "text": text,
                    "source_event": event_id,
                    "polarity": polarity,
                    "timestamp": now,
                    "is_dispute_fact": True,
                },
            )

    log.info(
        "dispute_extractor: cust=%s event=%s facts=%d (negative-skewed)",
        customer_id, event_id, len(fact_entries),
    )
    return {
        "tool": "extract_dispute_reasons",
        "facts_extracted": len(fact_entries),
        "event_embedded": True,
        "is_dispute": True,
    }


def make_extract_dispute_reasons_tool(
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
):
    """Strands @tool wrapper. The agent calls this for return/complaint events."""
    from strands import tool

    @tool
    def extract_dispute_reasons_tool(
        customer_id: str, event_text: str, event_id: str,
    ) -> dict:
        """Extract dispute-specific facts from a return / complaint / refund event.

        Use this instead of analyze_behavior_tool when event_type is one of:
        return, complaint, refund, support_ticket, or any event indicating
        customer dissatisfaction. The extracted facts are skewed toward
        polarity=-1 (rejections) and polarity=+1 (revealed preferences),
        which the recommender uses to avoid re-suggesting rejected items.

        Args:
            customer_id: the customer the event belongs to
            event_text: redacted event text (PII already removed)
            event_id: the event's unique ID

        Returns:
            dict with 'facts_extracted' (int), 'event_embedded' (bool),
            'is_dispute' (True), 'tool' ('extract_dispute_reasons').
        """
        return extract_dispute_reasons(customer_id, event_text, event_id, bedrock, vectors)

    return extract_dispute_reasons_tool
