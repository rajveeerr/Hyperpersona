"""Analyzer: fact extraction + embedding + storage.

Real Claude returns a JSON array of {"text": ..., "polarity": -1|0|1}.
Mock Bedrock returns a non-JSON stub; we fall back to a single canned fact
so the wiring still works end-to-end.
"""

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
    "Extract atomic facts ABOUT THE CUSTOMER from this event. Return a JSON "
    "array of {\"text\", \"polarity\"} objects. Maximum 5 facts.\n\n"
    "polarity describes the customer's sentiment toward the subject of the fact:\n"
    "   1  → customer prefers / likes / wants\n"
    "   0  → neutral / informational\n"
    "  -1  → customer dislikes / avoids / returned\n\n"
    "Each fact must be a short declarative sentence (8 words or fewer) about "
    "the customer, not about the event itself. Return ONLY the JSON array — "
    "no prose, no markdown, no explanation.\n\n"
    "Examples:\n"
    '  Event "purchase: Salomon X Ultra trail running shoes"\n'
    '    → [{"text": "owns Salomon X Ultra", "polarity": 0},\n'
    '       {"text": "interested in trail running", "polarity": 1}]\n'
    '  Event "return: Nike Pegasus, reason: poor fit"\n'
    '    → [{"text": "rejected Nike Pegasus", "polarity": -1},\n'
    '       {"text": "fit matters to this customer", "polarity": 1}]\n'
    '  Event "search: waterproof hiking boots size 11"\n'
    '    → [{"text": "shopping for waterproof hiking boots", "polarity": 1},\n'
    '       {"text": "wears size 11", "polarity": 0}]'
)

_PROMPT_TEMPLATE = "Event: {text}"


def _parse_facts(generated: str) -> list[dict]:
    """Find a JSON array in Claude's output. Returns an empty list on parse
    failure rather than injecting a stub fact — a malformed response should
    skip the analyzer for this event, not pollute the customer's fact graph
    with a generic placeholder ("interested in this product category") that
    the recommender would later treat as real signal."""
    try:
        match = re.search(r"\[.*?\]", generated, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    log.warning("analyzer: could not parse Claude facts; skipping event", extra={"raw_excerpt": (generated or "")[:160]})
    return []


def make_analyzer_tool(
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
):
    """Return a Strands @tool that closes over bedrock + vectors deps."""
    from strands import tool

    @tool
    def analyze_behavior_tool(
        customer_id: str, event_text: str, event_id: str,
    ) -> dict:
        """Extract behavioral facts from a customer event, embed them, store.

        Embeds the event text and stores it in behavior-embeddings. Asks
        Claude to extract atomic facts as JSON, embeds each fact, stores
        them in customer-facts. Returns a count of facts extracted.

        Args:
            customer_id: the customer the event belongs to
            event_text: redacted event text (PII already removed by privacy tool)
            event_id: the event's unique ID, used as the doc-id base

        Returns:
            dict with 'facts_extracted' (int) and 'event_embedded' (bool).
        """
        return analyze_behavior(customer_id, event_text, event_id, bedrock, vectors)

    return analyze_behavior_tool


def analyze_behavior(
    customer_id: str,
    event_text: str,
    event_id: str,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # 1. Embed the raw event and store in behavior_embeddings
    event_vector = bedrock.embed(event_text)
    vectors.upsert(
        COLLECTION_BEHAVIOR,
        event_id,
        event_vector,
        {"customer_id": customer_id, "text": event_text, "timestamp": now},
    )

    # 2. Ask Claude to extract facts
    raw = bedrock.generate(
        prompt=_PROMPT_TEMPLATE.format(text=event_text),
        system=_SYSTEM,
    )
    facts = _parse_facts(raw)

    # 3. Embed all facts in one batched call (parallel under the hood for real
    # Bedrock; sequential for mock). Wall-clock time goes from N×500ms to
    # ~max(call_latency) regardless of fact count.
    # Doc id = event_id + sha256(fact_text), so retries overwrite rather than
    # duplicate.
    fact_entries: list[tuple[str, str, int]] = []  # (doc_id, text, polarity)
    for fact in facts:
        fact_text = (fact or {}).get("text", "").strip()
        if not fact_text:
            continue
        digest = hashlib.sha256(fact_text.encode("utf-8")).hexdigest()[:16]
        doc_id = f"{event_id}:{digest}"
        fact_entries.append((doc_id, fact_text, fact.get("polarity", 0)))

    if fact_entries:
        fact_texts = [text for (_, text, _) in fact_entries]
        fact_vectors = bedrock.embed_batch(fact_texts)
        for (doc_id, fact_text, polarity), vec in zip(fact_entries, fact_vectors):
            vectors.upsert(
                COLLECTION_FACTS,
                doc_id,
                vec,
                {
                    "customer_id": customer_id,
                    "text": fact_text,
                    "source_event": event_id,
                    "polarity": polarity,
                    "timestamp": now,
                },
            )

    stored = len(fact_entries)
    log.info("analyzer: cust=%s event=%s facts=%d (batched)", customer_id, event_id, stored)
    return {"facts_extracted": stored, "event_embedded": True}
