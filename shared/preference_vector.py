"""Build a single user-preference vector from ACE-ranked facts.

Used by the complement pipeline to bias product KNN toward what the customer
has shown positive signal for and away from what they've shown negative signal
for. Output is a unit-normalized 1024-dim vector that gets blended with the
cart embedding via COMPLEMENT_PREF_WEIGHT.

Returns None for empty / cold-start input so callers can fall back to pure
cart-embedding KNN without a special branch.
"""

from __future__ import annotations

import math

from .bedrock import BedrockClientProtocol


def _polarity_sign(polarity: int | float | None) -> int:
    # -1 pulls candidates AWAY; 0 (neutral) and +1 both pull TOWARD. Treating
    # neutral as positive keeps signal that the customer engaged with the topic
    # at all — only explicit negatives flip the sign.
    return -1 if polarity == -1 else 1


def _l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _normalize(vec: list[float]) -> list[float]:
    n = _l2_norm(vec)
    if n == 0:
        return vec
    return [x / n for x in vec]


def build_preference_vector(
    ranked_facts: list[dict],
    bedrock: BedrockClientProtocol,
) -> list[float] | None:
    """Weighted-sum of fact embeddings, signed by polarity.

    Each fact dict is expected to carry at least 'text' (str) and
    'combined_score' (float, from ACE ranking). 'polarity' is optional;
    missing or 0 is treated as a positive (toward) pull, -1 as negative.

    Returns a unit-normalized vector matching the embedding dimension, or
    None when there are no usable facts (cold start, all-zero scores, etc.).
    """
    usable = [
        f for f in ranked_facts
        if f.get("text") and float(f.get("combined_score", 0.0)) > 0
    ]
    if not usable:
        return None

    vectors = bedrock.embed_batch([f["text"] for f in usable])
    if not vectors:
        return None
    dim = len(vectors[0])
    if dim == 0:
        return None

    acc = [0.0] * dim
    weight_total = 0.0
    for fact, vec in zip(usable, vectors):
        score = float(fact["combined_score"])
        sign = _polarity_sign(fact.get("polarity"))
        weight = score * sign
        unit = _normalize(list(vec))
        for i, x in enumerate(unit):
            acc[i] += weight * x
        weight_total += abs(weight)

    if weight_total == 0:
        return None

    avg = [x / weight_total for x in acc]
    if _l2_norm(avg) == 0:
        # Positive and negative weights canceled to a zero direction; treat
        # as cold-start so the caller falls back to pure cart-embedding.
        return None
    return _normalize(avg)
