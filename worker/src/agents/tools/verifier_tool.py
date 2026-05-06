"""Verifier: chain-of-verification.

Reads the draft offer + the actual source facts the recommender used,
and checks every concrete claim against the source. If every claim is
supported, replies VALID and the draft passes through. If any claim
isn't supported, rewrites the draft to remove or fix the unsupported
claim — keeps accurate parts intact.

source_context is built by recommender_tool.build_verifier_source_context
so the verifier sees the real fact + behavior + summary lines, not just
counts.
"""

import logging

from shared.bedrock import BedrockClientProtocol

log = logging.getLogger(__name__)

_SYSTEM = (
    "You verify a recommendation draft against source facts and behavior.\n\n"
    "For each specific claim in the draft (product names, brands, "
    "attributes, prices, discounts, promotions, features), find supporting "
    "evidence in the SOURCE data below. A claim is supported only if a "
    "source line directly mentions or implies it.\n\n"
    "If every concrete claim is supported: reply with the single word VALID.\n"
    "If any claim is unsupported: rewrite the draft to remove or fix the "
    "unsupported claim, keeping the accurate parts intact. Do not add new "
    "claims. Do not invent prices, discount percentages, or features that "
    "aren't in the source. Output the corrected draft as plain prose, "
    "one sentence, no markdown."
)


def make_verifier_tool(bedrock: BedrockClientProtocol):
    """Return a Strands @tool that closes over the bedrock dependency."""
    from strands import tool

    @tool
    def verify_recommendation_tool(draft_offer: str, source_context: str) -> dict:
        """Fact-check a draft offer against the source data.

        If every concrete claim is supported, returns status='valid' and
        passes the draft through unchanged. Otherwise returns
        status='corrected' with a rewritten offer that removes or fixes
        unsupported claims.

        Args:
            draft_offer: the recommendation text to verify
            source_context: structured source data (facts, behaviors,
                summaries, conflicts) that the recommendation should
                ground in. Built by
                recommender_tool.build_verifier_source_context.

        Returns:
            dict with 'status' ('valid'|'corrected') and 'final_offer' (str).
        """
        return verify_recommendation(draft_offer, source_context, bedrock)

    return verify_recommendation_tool


def verify_recommendation(
    draft_offer: str,
    source_context: str,
    bedrock: BedrockClientProtocol,
) -> dict:
    prompt = (
        f"{source_context}\n\n"
        f"DRAFT TO VERIFY:\n{draft_offer}\n\n"
        "For every concrete claim in the draft (products, brands, prices, "
        "discounts, features, promotions), find a matching source line. "
        "If even one claim is unsupported, output the corrected draft. "
        "Otherwise reply with the single word VALID."
    )
    verdict = bedrock.generate(prompt=prompt, system=_SYSTEM).strip()

    if verdict.upper().startswith("VALID"):
        log.info("verifier: status=valid")
        return {"status": "valid", "final_offer": draft_offer}

    log.info("verifier: status=corrected (draft had unsupported claims)")
    return {"status": "corrected", "final_offer": verdict}
