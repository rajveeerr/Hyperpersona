"""clarify_intent_tool — ask the customer instead of guessing.

The Strands recommend supervisor's orchestrator picks this tool when ACE
returned 3 or more conflict keys (the customer's signals contradict on 3+
topics). Instead of forcing an offer that's likely to be wrong, we
generate a short clarifying question and return that as the response.

This is a product feature competitors don't have. Amazon and Flipkart
will average the conflicting signals into "moderate preference"; we
explicitly recognize that the customer is sending mixed signals and
ask them.

Cost: 1 Sonnet call (~$0.006). Cheaper than a wrong Opus offer that
the customer ignores or returns from.
"""

from __future__ import annotations

import logging

from shared.bedrock import BedrockClientProtocol

log = logging.getLogger(__name__)


_SYSTEM = (
    "You generate a single, short clarifying question (1 sentence, ≤25 words) "
    "for an ecommerce customer whose recent signals contradict each other. "
    "The question should help the customer disambiguate their current intent.\n\n"
    "Strict rules:\n"
    "  - Output ONLY the question text. No preamble, no markdown.\n"
    "  - Use 2nd person (\"you\").\n"
    "  - Reference the conflict topic concretely if the topic name is meaningful.\n"
    "  - Be helpful, not interrogating. The question should feel like a friendly "
    "shop assistant, not a survey."
)


def generate_clarifying_question(
    context: str,
    conflicts: list[str],
    bedrock: BedrockClientProtocol,
) -> dict:
    """Ask Sonnet to write one clarifying question for a high-conflict customer."""
    if not conflicts:
        return {
            "tool": "clarify_intent",
            "offer": "What kind of item are you looking for today?",
            "clarifying_question": True,
            "conflicts": [],
        }

    prompt = (
        f"Customer context: {context}\n"
        f"Recent conflicting signals on these topics: {', '.join(conflicts[:5])}\n\n"
        "Write one short clarifying question to ask the customer."
    )
    question = bedrock.generate(
        prompt=prompt, system=_SYSTEM, max_tokens=80,
    ).strip()

    if not question:
        question = (
            "We've noticed mixed signals from your recent activity — "
            f"could you tell us more about what you want for {context}?"
        )

    log.info("clarify_intent: conflicts=%d question_len=%d",
             len(conflicts), len(question))
    return {
        "tool": "clarify_intent",
        "offer": question,
        "clarifying_question": True,
        "conflicts": conflicts,
    }


def make_clarify_intent_tool(bedrock: BedrockClientProtocol):
    """Strands @tool wrapper. Agent calls this when conflicts ≥ 3."""
    from strands import tool

    @tool
    def clarify_intent_tool(context: str, conflicts: list[str]) -> dict:
        """Ask the customer a clarifying question instead of guessing an offer.

        Use this ONLY when generate_recommendation_tool returned conflicts list
        with 3 or more entries — that means the customer's history contradicts
        itself on multiple topics and any offer we generate is likely wrong.

        After calling this tool, do NOT call verify_recommendation_tool — there
        is no offer to verify. The clarifying question IS the response.

        Args:
            context: the situation/intent the customer expressed
            conflicts: the list of conflict topic keys from the recommender

        Returns:
            dict with 'offer' (the clarifying question), 'clarifying_question'
            (True), 'conflicts' (the input list).
        """
        return generate_clarifying_question(context, conflicts, bedrock)

    return clarify_intent_tool
