"""Product review endpoints (UGC).

Three routes under /catalog/products/{slug}:
  - GET    .../reviews                       paginated list
  - POST   .../reviews                       create (one-per-customer-per-SKU)
  - PUT    .../reviews/{reviewId}/helpful    helpful / not_helpful vote
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.reviews import (
    CreateProductReviewBody,
    SetReviewHelpfulBody,
)
from ..services.reviews import ReviewsService

router = APIRouter()


def _service(request: Request) -> ReviewsService:
    return ReviewsService(dynamo=dynamo, snapshot=request.app.state.catalog)


def _serialize(model) -> JSONResponse:
    payload = model.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/catalog/products/{slug}/reviews")
def list_reviews(
    request: Request,
    slug: str,
    page: int = 1,
    pageSize: int = Query(default=10, ge=1, le=50),
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).list_reviews(slug, page, pageSize, customer_id))


@router.post("/catalog/products/{slug}/reviews")
def create_review(
    request: Request,
    slug: str,
    body: CreateProductReviewBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).create_review(slug, body, customer_id))


@router.put("/catalog/products/{slug}/reviews/{review_id}/helpful")
def set_helpful(
    request: Request,
    slug: str,
    review_id: str,
    body: SetReviewHelpfulBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).set_helpful(slug, review_id, body, customer_id))
