"""Handle generate_recommendation jobs.

Pipeline:
  1. Run the recommend supervisor (manual or strands) → offer text +
     verifier status + ACE-ranked facts.
  2. Pass those ranked facts through the products picker → personalized
     in-stock product cards via blended-KNN over OpenSearch product-catalog.
  3. Build a single 'Because you ...' personalization heading from the
     top Prefers fact (or null for cold start).
  4. Strip the internal `ranked_facts` field, merge picker output, push
     to result:{job_id} for the waiting server.
"""

import json
import logging
import time

from shared.queue import push_result

from ..agents.tools import products_picker_tool

log = logging.getLogger(__name__)


def _build_personalization_reason(ranked_facts: list[dict]) -> str | None:
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


def _humanize_slug(slug: str) -> str:
    """Convert a context slug like ``trail_running`` → ``trail running``.

    The /recommend context strings are normalized to lowercase + underscores
    by the FE (`Context.productPage` etc.). Strip surface prefixes before
    calling.
    """
    return slug.replace("_", " ").replace("-", " ").strip()


def _dominant_category(products: list[dict]) -> str | None:
    """Return the most common ``category`` among returned products.

    Used as a content-derived label when the request context didn't carry
    a category slug (e.g., cart, wishlist, post-purchase rails).
    """
    if not products:
        return None
    counts: dict[str, int] = {}
    for p in products:
        cat = (p.get("category") or "").strip()
        if not cat:
            continue
        counts[cat] = counts.get(cat, 0) + 1
    if not counts:
        return None
    top_cat, _ = max(counts.items(), key=lambda kv: kv[1])
    return _humanize_slug(top_cat)


def _build_rail_copy(
    context: str,
    products: list[dict],
    personalization_reason: str | None,
) -> dict:
    """Surface-aware rail copy: ``{eyebrow, headline, subtitle}``.

    The FE used to hardcode these per page; centralizing here means a
    single edit changes the wording across every surface and lets us
    weave the requested category (from `context`) or the dominant
    category (from `products`) into the headline.

    `subtitle` prefers the personalization_reason; otherwise falls back to
    a content-derived line so the slot never feels like filler.
    """
    surface, _, slug = context.partition(":")
    slug = slug.strip()
    requested_category = _humanize_slug(slug) if slug and slug != "general" else None
    category_label = requested_category or _dominant_category(products)

    # Generic-mode label rendered as a small chip next to the headline.
    # When personalization fired, the headline already carries the
    # "Because you ..." signal so the chip is suppressed (None). When
    # personalization is OFF, surface a surface-tuned label that's
    # honest but inviting — replaces the old hardcoded "Generic mode".
    if surface == "product_page":
        eyebrow = "Suggested next"
        headline = (
            f"Pieces that complete the {category_label} story"
            if category_label
            else "Pieces that complete the story"
        )
        fallback_subtitle = (
            f"Hand-picked complements for {category_label}."
            if category_label
            else "Hand-picked complements to round out the look."
        )
        generic_label = "Catalog pairings"
    elif surface == "homepage":
        eyebrow = "Recommended for you"
        headline = (
            f"Picks shaped by your interest in {category_label}"
            if category_label
            else "Picks shaped by your signals"
        )
        fallback_subtitle = "A starting point — your tiles will personalize as you browse."
        generic_label = "Editor's picks"
    elif surface == "category":
        eyebrow = "Recommended"
        headline = (
            f"Worth a closer look in {category_label}"
            if category_label
            else "Worth a closer look in this category"
        )
        fallback_subtitle = "Top-performing items others in this category love."
        generic_label = "Top in this category"
    elif surface == "search":
        eyebrow = "You might also like"
        headline = (
            f"More {category_label} picks worth a glance"
            if category_label
            else "More picks worth a glance"
        )
        fallback_subtitle = "Curated picks based on your search."
        generic_label = "Curated picks"
    elif surface == "cart_active":
        eyebrow = "Pairs well"
        headline = (
            f"Pairs well with the {category_label} in your bag"
            if category_label
            else "Pairs well with what's in your bag"
        )
        fallback_subtitle = "Frequently bought together with items you've added."
        generic_label = "Popular pairings"
    elif surface == "cart_empty":
        eyebrow = "Curated"
        headline = "Worth a look while your bag is empty"
        fallback_subtitle = "Quick favorites to start a new bag."
        generic_label = "Trending now"
    elif surface == "post_purchase":
        eyebrow = "Curated for you"
        headline = (
            f"Worth considering after your {category_label} order"
            if category_label
            else "Worth considering for next time"
        )
        fallback_subtitle = "Pair-with picks for your latest order."
        generic_label = "Editor's picks"
    elif surface == "wishlist_active":
        eyebrow = "Recommended"
        headline = (
            f"More {category_label} to consider"
            if category_label
            else "More to consider for your wishlist"
        )
        fallback_subtitle = "Items in line with what you've already saved."
        generic_label = "More like this"
    elif surface == "no_results":
        eyebrow = "Curated"
        headline = "While you're here, take a look at these"
        fallback_subtitle = "A few staples we'd recommend in their place."
        generic_label = "Trending now"
    elif surface == "email":
        eyebrow = "From the editors"
        headline = (
            f"Fresh {category_label} picks for you"
            if category_label
            else "Fresh picks for you"
        )
        fallback_subtitle = "Curated for your inbox."
        generic_label = "Editor's picks"
    else:
        eyebrow = "Recommended"
        headline = (
            f"More {category_label} we think you'll like"
            if category_label
            else "More we think you'll like"
        )
        fallback_subtitle = "Curated for you."
        generic_label = "Curated picks"

    subtitle = personalization_reason or fallback_subtitle
    mode_label = None if personalization_reason else generic_label
    return {
        "eyebrow": eyebrow,
        "headline": headline,
        "subtitle": subtitle,
        "mode_label": mode_label,
    }


def handle(job: dict, ctx: dict) -> None:
    job_id = job["job_id"]
    payload = job["payload"]
    customer_id = payload["customer_id"]
    context = payload["context"]

    supervisor = ctx["recommend_supervisor"]
    redis_client = ctx["redis"]
    bedrock = ctx["bedrock"]
    vectors = ctx["vectors"]
    dynamo = ctx["dynamo"]
    tracer = ctx["tracer"]

    result = supervisor.run_recommend(job_id, customer_id, context)

    # Internal — used to seed the picker + heading; not returned publicly.
    ranked_facts = result.pop("ranked_facts", [])

    t0 = time.time()
    picker_out = products_picker_tool.pick_personalized_products(
        context=context,
        ranked_facts=ranked_facts,
        bedrock=bedrock,
        vectors=vectors,
        dynamo=dynamo,
    )
    duration_ms = (time.time() - t0) * 1000
    tracer.log(
        job_id, "products_picker", "pick_products",
        {"context_len": len(context), "facts_in": len(ranked_facts)},
        {
            "products_returned": len(picker_out["products"]),
            "candidates_considered": picker_out["candidates_considered"],
        },
        duration_ms, "ok",
    )

    result["products"] = picker_out["products"]
    result["candidates_considered"] = picker_out["candidates_considered"]
    personalization_reason = _build_personalization_reason(ranked_facts)
    result["personalization_reason"] = personalization_reason
    result["rail"] = _build_rail_copy(
        context, picker_out["products"], personalization_reason,
    )
    result["job_id"] = job_id

    push_result(redis_client, job_id, json.dumps(result))
    log.info(
        "recommendation result pushed for job %s (products=%d, facts=%d)",
        job_id, len(picker_out["products"]), len(ranked_facts),
    )
