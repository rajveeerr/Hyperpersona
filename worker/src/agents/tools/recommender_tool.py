"""Recommender: retrieve facts + behaviors, ACE-rank, generate offer."""

import logging

from shared.ace_ranking import rank_facts
from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_BEHAVIOR, COLLECTION_FACTS, COLLECTION_SESSIONS
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)

_SYSTEM = (
    "You are HyperPersona's recommendation agent. Write ONE personalized "
    "offer (1 sentence, plain text, no markdown, no emoji, no bullet points).\n\n"
    "Strict rules:\n"
    "  - Use ONLY the facts, behaviors, and summaries provided. Do NOT "
    "fabricate discount percentages, prices, promotions, or product features "
    "that aren't in the source data. If you cannot cite a specific source "
    "line for a number, omit the number.\n"
    "  - When CONFLICTS are listed, weight the more-recent signal — do not "
    "recommend the older preference even if it appears more often.\n"
    "  - If NO facts and NO behaviors are available (cold start), open with "
    "\"For your {context}, ...\" and write a generic offer keyed to context "
    "only. Do not pretend to know preferences you cannot see.\n"
    "  - Be specific about the product or category. Do not write \"some "
    "items you might like\"-style filler."
)


def _build_prompt(
    facts: list[dict],
    behaviors: list[dict],
    summaries: list[dict],
    context: str,
    conflicts: list[str],
) -> str:
    """Render the source data the model is allowed to draw from.

    Format is structured with explicit section headers so the model can
    reason about which signal it's using, and the verifier (called next)
    can cite the same lines.
    """
    fact_lines = (
        "\n".join(
            f"- {f['text']} (polarity={f.get('polarity', 0)})"
            for f in facts
        )
        or "(none)"
    )
    behav_lines = "\n".join(f"- {b['text']}" for b in behaviors) or "(none)"
    summary_lines = "\n".join(f"- {s['text']}" for s in summaries) or "(none)"

    cold_start = not facts and not behaviors and not summaries
    cold_start_note = (
        "\nNOTE: cold-start customer (no stored preferences). Open with "
        f'"For your {context}, ..." and write a generic offer keyed only '
        "to the context above. Do NOT pretend to know personal preferences."
        if cold_start else ""
    )

    conflict_note = ""
    if conflicts:
        conflict_note = (
            f"\nCONFLICTS DETECTED on these topics: {', '.join(conflicts)}.\n"
            "Weight the more-recent signal. Do not recommend the older "
            "preference even if it has more total mentions.\n"
        )

    return (
        f"CUSTOMER CONTEXT:\n{context}\n\n"
        f"KNOWN FACTS ABOUT THIS CUSTOMER:\n{fact_lines}\n\n"
        f"SESSION ACTIVITY ROLLUPS:\n{summary_lines}\n\n"
        f"RECENT HIGH-SIGNAL BEHAVIOR:\n{behav_lines}\n"
        f"{conflict_note}"
        f"{cold_start_note}\n\n"
        "Write ONE personalized offer in a single sentence."
    )


def build_verifier_source_context(rec_result: dict, context: str) -> str:
    """Render the same source data as a verification payload.

    The verifier (Opus 4.5) reads this to fact-check every concrete claim
    in the draft offer. This is the difference between a real verifier
    and a theatrical one — it has the actual facts, not just counts.
    """
    parts: list[str] = [f"CUSTOMER CONTEXT:\n{context}", ""]

    ranked = rec_result.get("ranked_facts", [])
    if ranked:
        parts.append(f"SOURCE FACTS USED ({len(ranked)}):")
        for f in ranked:
            parts.append(f"- {f.get('text', '?')} (polarity={f.get('polarity', 0)})")
    else:
        parts.append("SOURCE FACTS USED: none")
    parts.append("")

    behaviors = rec_result.get("behaviors_text") or []
    if behaviors:
        parts.append(f"RECENT BEHAVIOR ({len(behaviors)}):")
        for b in behaviors:
            parts.append(f"- {b}")
    else:
        parts.append("RECENT BEHAVIOR: none")
    parts.append("")

    summaries = rec_result.get("summaries_text") or []
    if summaries:
        parts.append(f"SESSION SUMMARIES ({len(summaries)}):")
        for s in summaries:
            parts.append(f"- {s}")
    else:
        parts.append("SESSION SUMMARIES: none")
    parts.append("")

    conflicts = rec_result.get("conflicts") or []
    parts.append(f"CONFLICTS DETECTED: {', '.join(conflicts) if conflicts else 'none'}")

    return "\n".join(parts)


def make_recommender_tool(
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
):
    """Return a Strands @tool that closes over bedrock + vectors deps."""
    from strands import tool

    @tool
    def generate_recommendation_tool(customer_id: str, context: str) -> dict:
        """Generate a personalized offer based on stored facts and behavior.

        Retrieves customer facts + recent behavior + session summaries from
        vector memory, ACE-ranks the facts (recency, polarity, conflict
        detection), and asks Claude to write a one-sentence offer grounded
        only in that retrieved data.

        Args:
            customer_id: the customer to generate a recommendation for
            context: the situation/intent (e.g., "looking for outdoor gear")

        Returns:
            dict with 'offer' (str), 'facts_used', 'behaviors_used',
            'conflicts', plus internal 'ranked_facts'/'behaviors_text'/
            'summaries_text' the verifier consumes.
        """
        return generate_recommendation(customer_id, context, bedrock, vectors)

    return generate_recommendation_tool


def generate_recommendation(
    customer_id: str,
    context: str,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
) -> dict:
    query = bedrock.embed(context)

    # Pull a wider set of facts so ACE has options to dedupe and rank.
    raw_facts = vectors.search(
        COLLECTION_FACTS, query, k=20, filter_customer=customer_id
    )
    ranked, conflicts = rank_facts(raw_facts)

    behaviors = vectors.search(
        COLLECTION_BEHAVIOR, query, k=4, filter_customer=customer_id
    )

    # Session summaries cover the cheap-path (low-signal) events. Without this
    # the tiered processing in Step 2 stores them but the recommender ignores
    # them. k=3 is enough — each summary already aggregates many events.
    summaries = vectors.search(
        COLLECTION_SESSIONS, query, k=3, filter_customer=customer_id
    )

    prompt = _build_prompt(ranked, behaviors, summaries, context, conflicts)
    offer = bedrock.generate(prompt=prompt, system=_SYSTEM)

    log.info(
        "recommender: cust=%s retrieved=%d ranked=%d behaviors=%d summaries=%d conflicts=%d",
        customer_id, len(raw_facts), len(ranked), len(behaviors), len(summaries), len(conflicts),
    )
    return {
        "offer": offer,
        "facts_retrieved": len(raw_facts),
        "facts_used": len(ranked),
        "behaviors_used": len(behaviors),
        "summaries_used": len(summaries),
        "conflicts": conflicts,
        # Internal — the supervisor passes these to the verifier so it can
        # actually fact-check claims, and the products picker reuses
        # ranked_facts to seed its candidate scoring. The handler strips
        # them before pushing the public response.
        "ranked_facts": ranked,
        "behaviors_text": [b.get("text", "") for b in behaviors if b.get("text")],
        "summaries_text": [s.get("text", "") for s in summaries if s.get("text")],
    }
