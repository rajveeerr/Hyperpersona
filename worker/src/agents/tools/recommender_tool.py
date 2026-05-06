"""Recommender: retrieve facts + behaviors, ACE-rank, generate offer."""

import logging

from shared.ace_ranking import rank_facts
from shared.bedrock import BedrockClientProtocol
from shared.constants import COLLECTION_BEHAVIOR, COLLECTION_FACTS, COLLECTION_SESSIONS
from shared.vector_store import VectorStoreProtocol

log = logging.getLogger(__name__)

_SYSTEM = (
    "You are HyperPersona's recommendation agent. Generate one personalized "
    "offer based ONLY on the provided facts and recent behavior. Do not "
    "invent facts. Be specific and concise."
)


def _build_prompt(
    facts: list[dict],
    behaviors: list[dict],
    summaries: list[dict],
    context: str,
    conflicts: list[str],
) -> str:
    fact_lines = "\n".join(f"- {f['text']}" for f in facts) or "(no facts on file)"
    behav_lines = "\n".join(f"- {b['text']}" for b in behaviors) or "(no recent behavior)"
    summary_lines = "\n".join(f"- {s['text']}" for s in summaries) or "(no session summaries)"
    conflict_note = ""
    if conflicts:
        conflict_note = (
            f"\nNote: customer has conflicting preferences on these topics: "
            f"{', '.join(conflicts)}. Prefer the more recent signal.\n"
        )
    return (
        f"Customer context: {context}\n\n"
        f"Known facts about this customer:\n{fact_lines}\n\n"
        f"Session activity rollups:\n{summary_lines}\n\n"
        f"Recent high-signal behavior:\n{behav_lines}\n"
        f"{conflict_note}\n"
        "Write a single 1-sentence personalized offer."
    )


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
    }
