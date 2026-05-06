"""Catalog read endpoints — categories, popular, list, facets, PDP.

All requests are served from the in-memory CatalogSnapshot loaded at
startup from DynamoDB. Filter + facet semantics match the frontend MSW
mocks at apps/web/src/mocks/handlers.ts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.catalog import (
    CatalogFacetGroup,
    Category,
    Product,
    ProductListResponse,
    SortOrder,
)
from ..services.catalog_filter import (
    FilterParams,
    build_facets,
    filter_products_response,
)
from ..services.catalog_snapshot import CatalogSnapshot
from ..services.reviews import viewer_review_for

router = APIRouter()


def _snapshot(request: Request) -> CatalogSnapshot:
    return request.app.state.catalog


def _serialize(model) -> JSONResponse:
    """Pydantic camelCase serialization with by_alias=True."""
    if isinstance(model, list):
        payload = [m.model_dump(by_alias=True, exclude_none=True) for m in model]
    else:
        payload = model.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/catalog/categories")
def list_categories(request: Request) -> JSONResponse:
    cats: list[Category] = _snapshot(request).list_categories()
    return _serialize(cats)


@router.get("/catalog/popular")
def list_popular(request: Request) -> JSONResponse:
    products = _snapshot(request).list_products()
    # "Most popular" = highest reviewCount, capped at 6, same shape every shopper sees.
    top = sorted(products, key=lambda p: p.review_count, reverse=True)[:6]
    return _serialize(top)


@router.get("/catalog/products")
def list_products(
    request: Request,
    category: str | None = None,
    q: str | None = None,
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
    response = filter_products_response(
        _snapshot(request).list_products(),
        params,
        sort=sort,
        page=page,
        page_size=pageSize,
        personalized=False,
    )
    return _serialize(response)


@router.get("/catalog/facets")
def list_facets(
    request: Request,
    category: str | None = None,
    q: str | None = None,
    brand: str | None = None,
    vertical: str | None = None,
    freeDelivery: bool | None = Query(default=None),
    tags: str | None = None,
    minPrice: float | None = None,
    maxPrice: float | None = None,
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
    facets: list[CatalogFacetGroup] = build_facets(_snapshot(request).list_products(), params)
    return _serialize(facets)


@router.get("/catalog/products/{slug}")
def get_product(
    request: Request,
    slug: str,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    product: Product | None = _snapshot(request).get_product(slug)
    if not product:
        raise HTTPException(status_code=404, detail="product not found")
    # Project the viewer's own review onto the PDP shape (or None if
    # they haven't reviewed this SKU). One Query on the GSI.
    viewer = viewer_review_for(dynamo, slug, customer_id)
    if viewer is not None:
        product = product.model_copy(update={"viewer_review": viewer})
    return _serialize(product)
