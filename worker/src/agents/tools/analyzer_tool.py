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


_SYSTEM = "Return only a JSON array. Each fact is one short declarative sentence."

_PROMPT_TEMPLATE = (
    "Extract atomic facts from this customer event text. Return a JSON array "
    "of objects with keys 'text' (short declarative sentence) and 'polarity' "
    "(-1, 0, or 1).\n\nEvent: {text}"
)


def _parse_facts(generated: str) -> list[dict]:
    """Find a JSON array in Claude's output. Fall back to a stub on failure."""
    try:
        match = re.search(r"\[.*?\]", generated, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # mock-mode fallback so the rest of the pipeline has at least one fact
    return [{"text": "interested in this product category", "polarity": 1}]


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
