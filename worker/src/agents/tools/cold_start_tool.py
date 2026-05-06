"""cold_start_popular_tool — return trending items when we have zero customer data.

The Strands recommend supervisor's orchestrator picks this tool when the
recommender returned 0 ranked_facts AND 0 behaviors. Instead of paying
for an Opus call to generate a "personalized" offer based on nothing,
we read recent popular products from DynamoDB and return a context-only
offer text.

Net effect: cold-start customers cost ~$0 on the LLM side instead of
~$0.085. And the offer is honest ("here's what's trending") instead
of pretending we know preferences we can't see.
"""

from __future__ import annotations

import logging

from shared.dynamo import DynamoClient

log = logging.getLogger(__name__)


def cold_start_recommendations(
    context: str,
    dynamo: DynamoClient,
    limit: int = 5,
) -> dict:
    """Read top products from the catalog and format a generic offer.

    No LLM call — we use a deterministic template so cold-start latency
    stays under 500ms total.
    """
    products: list[dict] = []
    try:
        scan_fn = getattr(dynamo, "scan_products", None)
        if callable(scan_fn):
            raw = scan_fn() or []
            # Take the first `limit`. Production deployment should swap this
            # for "trending" — recent purchase counts, etc.
            for row in raw[:limit]:
                products.append({
                    "slug": row.get("slug") or row.get("product_id") or "",
                    "name": row.get("name") or "",
                    "price": str(row.get("price") or ""),
                })
    except Exception as e:  # noqa: BLE001
        log.warning("cold_start: scan_products failed: %s", e)

    if products:
        names = ", ".join(p["name"] for p in products if p["name"])[:200]
        offer = (
            f"For your {context}, here are some of our most-loved items: {names}. "
            "Browse around — once you start clicking, your recommendations get personalized."
        )
    else:
        offer = (
            f"For your {context}, browse our latest collection. "
            "We'll personalize as you explore."
        )

    log.info("cold_start: products=%d", len(products))
    return {
        "tool": "cold_start_popular",
        "offer": offer,
        "products": products,
        "facts_used": 0,
        "behaviors_used": 0,
        "cold_start": True,
    }


def make_cold_start_tool(dynamo: DynamoClient):
    """Strands @tool wrapper. The agent calls this for new/empty customers."""
    from strands import tool

    @tool
    def cold_start_popular_tool(context: str) -> dict:
        """Return popular products as a generic offer for cold-start customers.

        Use this tool ONLY after generate_recommendation_tool has been called
        and returned 0 facts AND 0 behaviors — that means we have no signal
        for this customer, so paying for an Opus offer would be wasteful.

        After calling this tool, do NOT call verify_recommendation_tool — there
        are no claims about the customer to verify. Skip directly to returning
        a confirmation.

        Args:
            context: the situation/intent the customer expressed
                (e.g., "looking for outdoor gear")

        Returns:
            dict with 'offer' (generic offer text), 'products' (list),
            'cold_start' (True), 'facts_used' (0), 'behaviors_used' (0).
        """
        return cold_start_recommendations(context, dynamo)

    return cold_start_popular_tool
