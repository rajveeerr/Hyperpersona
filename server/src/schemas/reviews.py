"""Pydantic models for product reviews + helpful votes.

Mirrors the frontend contracts in apps/web/src/shared/api/contracts.ts:91-136.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewHelpfulVote = Literal["helpful", "not_helpful"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ProductReview(_CamelModel):
    id: str
    product_id: str = Field(alias="productId")
    author_display_name: str = Field(alias="authorDisplayName")
    rating: int
    title: str | None = None
    body: str
    created_at: str = Field(alias="createdAt")
    verified_purchase: bool | None = Field(default=None, alias="verifiedPurchase")
    helpful_count: int = Field(default=0, alias="helpfulCount")
    not_helpful_count: int = Field(default=0, alias="notHelpfulCount")
    viewer_helpful_vote: ReviewHelpfulVote | None = Field(default=None, alias="viewerHelpfulVote")


class ProductReviewsResponse(_CamelModel):
    items: list[ProductReview]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int


class CreateProductReviewBody(_CamelModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str = Field(min_length=4)


class ViewerProductReview(_CamelModel):
    """Compact projection returned alongside Product when the viewer has
    submitted a review for that SKU."""
    id: str
    rating: int
    title: str | None = None
    body: str
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class CreateProductReviewResponse(_CamelModel):
    review: ProductReview
    viewer_review: ViewerProductReview = Field(alias="viewerReview")


class SetReviewHelpfulBody(_CamelModel):
    vote: ReviewHelpfulVote


class SetReviewHelpfulResponse(_CamelModel):
    review_id: str = Field(alias="reviewId")
    helpful_count: int = Field(alias="helpfulCount")
    not_helpful_count: int = Field(alias="notHelpfulCount")
    viewer_helpful_vote: ReviewHelpfulVote = Field(alias="viewerHelpfulVote")
