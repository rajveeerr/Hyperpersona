"""Reviews service — list, create, helpful-vote.

Aggregate strategy: write-through. After a successful create_review, we
recompute the product's `rating` and `reviewCount` and push the new
values to both Dynamo (`update_product_review_aggregates`) and the
in-memory `CatalogSnapshot` (`bump_review_aggregates`). Vector + vector
metadata are NOT touched — see the catalog ↔ vector sync invariant in
catalog_writer.py for the carve-out reasoning.

Helpful-vote idempotence: the `set_helpful` flow reads the prior vote
(if any), computes the per-bucket deltas (-1 from prior, +1 to new),
writes the new vote row, and applies an atomic UpdateExpression on the
review's counters. Re-voting the same direction is a no-op.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from shared.dynamo import DynamoClient
from shared.schemas import new_uuid, utc_now_iso

from ..schemas.reviews import (
    CreateProductReviewBody,
    CreateProductReviewResponse,
    ProductReview,
    ProductReviewsResponse,
    ReviewHelpfulVote,
    SetReviewHelpfulBody,
    SetReviewHelpfulResponse,
    ViewerProductReview,
)
from .catalog_snapshot import CatalogSnapshot

log = logging.getLogger(__name__)


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


def _row_to_review(row: dict, viewer_vote: ReviewHelpfulVote | None = None) -> ProductReview:
    cleaned = _strip_dynamo_keys(row)
    # Drop fields the model doesn't expose (we stored them for GSI / ops).
    cleaned.pop("product_slug", None)
    cleaned.pop("customer_id", None)
    review = ProductReview.model_validate(cleaned)
    if viewer_vote is not None:
        review = review.model_copy(update={"viewer_helpful_vote": viewer_vote})
    return review


def _row_to_viewer_review(row: dict) -> ViewerProductReview:
    return ViewerProductReview.model_validate(_strip_dynamo_keys(row))


def _viewer_display_name(customer_id: str) -> str:
    """Demo-grade pseudonymization: 'Customer ' + last 4 of id. Real
    deployment would resolve from the customer profile."""
    tail = customer_id[-4:] if len(customer_id) > 4 else customer_id
    return f"Customer {tail.upper()}"


class ReviewsService:
    def __init__(self, dynamo: DynamoClient, snapshot: CatalogSnapshot) -> None:
        self._dynamo = dynamo
        self._snapshot = snapshot

    # --- list -----------------------------------------------------------

    def list_reviews(
        self,
        slug: str,
        page: int,
        page_size: int,
        viewer_id: str,
    ) -> ProductReviewsResponse:
        if not self._snapshot.get_product(slug):
            raise HTTPException(status_code=404, detail="product not found")

        rows = self._dynamo.list_reviews_for_product(slug)
        # Newest first.
        rows.sort(key=lambda r: r.get("createdAt") or r.get("created_at") or "", reverse=True)

        total = len(rows)
        page = max(1, page)
        page_size = min(50, max(1, page_size))
        start = (page - 1) * page_size
        page_rows = rows[start : start + page_size]

        items: list[ProductReview] = []
        for row in page_rows:
            vote_row = self._dynamo.get_vote(row["id"], viewer_id)
            vote = vote_row.get("vote") if vote_row else None
            items.append(_row_to_review(row, viewer_vote=vote))

        return ProductReviewsResponse(items=items, page=page, pageSize=page_size, total=total)

    # --- create ---------------------------------------------------------

    def create_review(
        self,
        slug: str,
        body: CreateProductReviewBody,
        viewer_id: str,
    ) -> CreateProductReviewResponse:
        product = self._snapshot.get_product(slug)
        if not product:
            raise HTTPException(status_code=404, detail="product not found")

        if self._dynamo.get_viewer_review(slug, viewer_id):
            raise HTTPException(
                status_code=409,
                detail="customer has already reviewed this product",
            )

        review_id = f"rev-{new_uuid()[:8]}"
        created_at = utc_now_iso()
        record = {
            "id": review_id,
            "productId": product.id,
            "authorDisplayName": _viewer_display_name(viewer_id),
            "rating": body.rating,
            "title": body.title,
            "body": body.body,
            "createdAt": created_at,
            "verifiedPurchase": False,
            "helpfulCount": 0,
            "notHelpfulCount": 0,
            "customer_id": viewer_id,
        }
        self._dynamo.put_review(slug, record)

        # Recompute aggregates from all reviews (small N, simple).
        self._recompute_aggregates(slug)

        review_payload = _row_to_review({**record, "PK": "", "SK": ""})
        viewer_payload = ViewerProductReview(
            id=review_id,
            rating=body.rating,
            title=body.title,
            body=body.body,
            createdAt=created_at,
        )
        return CreateProductReviewResponse(review=review_payload, viewerReview=viewer_payload)

    # --- helpful vote ---------------------------------------------------

    def set_helpful(
        self,
        slug: str,
        review_id: str,
        body: SetReviewHelpfulBody,
        viewer_id: str,
    ) -> SetReviewHelpfulResponse:
        review = self._dynamo.get_review(slug, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="review not found")

        # Voters can't mark their own review.
        if review.get("customer_id") == viewer_id:
            raise HTTPException(status_code=400, detail="cannot vote on your own review")

        prior_row = self._dynamo.get_vote(review_id, viewer_id)
        prior = prior_row.get("vote") if prior_row else None
        new_vote = body.vote

        helpful_delta = 0
        not_helpful_delta = 0
        if prior == "helpful":
            helpful_delta -= 1
        elif prior == "not_helpful":
            not_helpful_delta -= 1
        if new_vote == "helpful":
            helpful_delta += 1
        elif new_vote == "not_helpful":
            not_helpful_delta += 1

        # Persist the vote first (idempotent overwrite).
        self._dynamo.put_vote(review_id, viewer_id, new_vote)

        # Then bump the counters atomically. If deltas net to zero (e.g.
        # voting the same way twice), skip the write — the counters
        # already reflect the prior vote.
        if helpful_delta == 0 and not_helpful_delta == 0:
            updated = review
        else:
            updated = self._dynamo.update_review_counters(
                slug, review_id, helpful_delta, not_helpful_delta
            )

        return SetReviewHelpfulResponse(
            reviewId=review_id,
            helpfulCount=int(updated.get("helpfulCount", 0)),
            notHelpfulCount=int(updated.get("notHelpfulCount", 0)),
            viewerHelpfulVote=new_vote,
        )

    # --- internals ------------------------------------------------------

    def _recompute_aggregates(self, slug: str) -> None:
        rows = self._dynamo.list_reviews_for_product(slug)
        if not rows:
            return
        ratings = [float(r["rating"]) for r in rows if "rating" in r]
        if not ratings:
            return
        avg = round(sum(ratings) / len(ratings), 2)
        count = len(ratings)
        self._snapshot.bump_review_aggregates(slug, avg, count)


def viewer_review_for(
    dynamo: DynamoClient,
    slug: str,
    viewer_id: str | None,
) -> ViewerProductReview | None:
    """Helper used by the PDP route to project the viewer's own review
    (if any) onto the Product payload."""
    if not viewer_id:
        return None
    row = dynamo.get_viewer_review(slug, viewer_id)
    if not row:
        return None
    return _row_to_viewer_review(row)
