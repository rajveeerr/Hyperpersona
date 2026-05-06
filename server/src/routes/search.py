"""Product search — hybrid text + vector similarity.

Uses the same response shape as GET /catalog/products. When `q` is
present we KNN the product-catalog OpenSearch index and union with
substring matches; without `q` it behaves as a plain catalog listing.
"""

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..schemas.catalog import SortOrder
from ..services.catalog_filter import FilterParams
from ..services.catalog_snapshot import CatalogSnapshot
from ..services.product_search import hybrid_search

router = APIRouter()


def _snapshot(request: Request) -> CatalogSnapshot:
    return request.app.state.catalog


@router.get("/search")
def search(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    vertical: str | None = None,
    freeDelivery: bool | None = Query(default=None),
    tags: str | None = None,
    minPrice: float | None = None,
    maxPrice: float | None = None,
    sort: SortOrder = "featured",
    page: int = 1,
    pageSize: int = Query(default=12, ge=1, le=48),
) -> JSONResponse:
    params = FilterParams(
        category=category,
        q=q,
        brand=brand,
        vertical=vertical,
        free_delivery=freeDelivery,
        tags=tags,
        min_price=minPrice,
        max_price=maxPrice,
    )
    response = hybrid_search(
        all_products=_snapshot(request).list_products(),
        params=params,
        sort=sort,
        page=page,
        page_size=pageSize,
        personalized=False,
        bedrock=request.app.state.bedrock,
        vectors=request.app.state.vectors,
    )
    payload = response.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))
