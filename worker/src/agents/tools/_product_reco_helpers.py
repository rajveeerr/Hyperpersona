"""Shared helpers for the product-recommendation pipeline.

Both `generate_recommendation` (browsing-history rail) and
`generate_related_recommendation` (cart complements + price-tier substitutes)
need:

  - `build_personalization_reason` — a "Because you ..." heading derived from
    the highest-score Prefers fact, used as the rail title in the response.

  - `retrieve_ranked_facts` — pull top customer-facts via OpenSearch KNN over
    the seed vector, ACE-rank by recency × similarity, return top-N. Both
    handlers use this with identical parameters so it lives here.

Pure extractions — no behavioral change vs the original inline definitions.
"""

from __future__ import annotations

import logging

from shared.ace_ranking import rank_facts
from shared.constants import COLLECTION_FACTS

log = logging.getLogger(__name__)

# Tuning for the facts retrieval. Kept in this module (not constants.py) so
# the recommender's KNN tuning stays close to the call site that uses it.
FACTS_K = 15            # how many candidate facts to pull from OpenSearch
FACTS_TOP = 5           # how many ACE-ranked facts to pass downstream


def build_personalization_reason(ranked_facts: list[dict]) -> str | None:
    """Format the highest-score Prefers fact as a 2nd-person heading.

    Returns None for cold-start (no Prefers facts). The frontend renders a
    fallback heading like 'Recommended for you' in that case.

    Heuristic, not LLM. With real Bedrock we could add a tiny Haiku call to
    rewrite the heading into clean grammar; the heuristic is good enough
    for v1 and ships zero new Bedrock cost.
    """
    prefers = [
        f for f in ranked_facts
        if (f.get("polarity") or 0) >= 0 and f.get("text")
    ]
    if not prefers:
        return None
    # ace_ranking.rank_facts already sorts by combined_score desc, but be
    # explicit so the heading is stable if that ordering convention shifts.
    prefers.sort(key=lambda f: float(f.get("combined_score", 0)), reverse=True)
    top_text = prefers[0]["text"].strip()
    if not top_text:
        return None
    # Lowercase the leading character so "Likes hiking gear" reads as
    # "Because you likes hiking gear" — still grammatically rough but a
    # closer fit than "Because you Likes ...".
    if top_text[0].isupper() and (len(top_text) == 1 or not top_text[1].isupper()):
        top_text = top_text[0].lower() + top_text[1:]
    heading = f"Because you {top_text}"
    return heading[:90]


def retrieve_ranked_facts(
    customer_id: str,
    seed_vec: list[float],
    vectors,
    k: int = FACTS_K,
    top: int = FACTS_TOP,
) -> list[dict]:
    """Return up to `top` ACE-ranked fact dicts (text + polarity +
    combined_score). Empty for cold-start customers or on retrieval failure.
    """
    try:
        raw_facts = vectors.search(
            COLLECTION_FACTS, seed_vec, k=k, filter_customer=customer_id,
        )
    except Exception as e:
        log.warning("fact retrieval failed: %s", e)
        return []

    ranked, _conflicts = rank_facts(raw_facts)
    return [f for f in ranked[:top] if f.get("text")]
