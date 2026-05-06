"""Catalog filter + facet engine.

Python port of apps/web/src/mocks/handlers.ts:81-204
(applyProductFilters, buildFacets, filterProducts) — same per-group skip
semantics so a selected facet doesn't zero out its siblings (OR within a
facet group, AND across groups).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from ..schemas.catalog import (
    CatalogFacetGroup,
    CatalogFacetValue,
    Product,
    ProductListResponse,
    SortOrder,
)


def _vertical(p: Product) -> str:
    """Slug used by the 'vertical' filter dimension on the wire.

    Historically this read `p.vertical` (apparel/electronics/furniture/general)
    which produced 4 broad pills. With ~600 products spanning Mens/Womens/Kids
    /Beauty/Jewellery/Watches/Electronics/Kitchen, those 4 buckets were too
    coarse for browse — `Apparel & accessories` alone held >300 items.

    We now key off `p.department` (the seed data carries Mens, Womens, Beauty,
    Jewellery, Kids, Watches, Electronics, Kitchen, etc.). The URL param keeps
    its legacy name `vertical=` so the FE doesn't need to change.
    """
    return (p.department or "Other").lower()


def _matches_query(text: str | None, q: str) -> bool:
    if not text:
        return False
    return q.lower() in text.lower()


@dataclass(frozen=True)
class FilterParams:
    """All filter knobs the catalog/search endpoints accept. None means
    'no filter applied for this dimension'."""
    category: str | None = None
    q: str | None = None
    brand: str | None = None
    vertical: str | None = None  # comma-separated
    free_delivery: bool | None = None
    tags: str | None = None  # comma-separated
    min_price: float | None = None
    max_price: float | None = None


@dataclass(frozen=True)
class FilterSkip:
    """Per-facet exclusions used while computing facet counts."""
    vertical: bool = False
    free_delivery: bool = False


def apply_product_filters(
    products: Iterable[Product],
    params: FilterParams,
    skip: FilterSkip = FilterSkip(),
) -> list[Product]:
    out: list[Product] = list(products)

    if params.category:
        out = [p for p in out if p.category == params.category]

    if params.q:
        q = params.q
        out = [
            p
            for p in out
            if any(
                _matches_query(field, q)
                for field in [
                    p.name,
                    p.brand,
                    p.description,
                    *(p.tags or []),
                    *p.features,
                ]
            )
        ]

    if params.brand:
        b = params.brand.lower()
        out = [p for p in out if p.brand.lower() == b]

    if params.vertical and not skip.vertical:
        wanted = {v.strip() for v in params.vertical.split(",") if v.strip()}
        out = [p for p in out if _vertical(p) in wanted]

    if params.free_delivery is True and not skip.free_delivery:
        out = [p for p in out if p.free_delivery is True]

    if params.min_price is not None:
        out = [p for p in out if p.price >= params.min_price]
    if params.max_price is not None:
        out = [p for p in out if p.price <= params.max_price]

    if params.tags:
        wanted = [t.strip().lower() for t in params.tags.split(",") if t.strip()]
        if wanted:
            def _has_any_tag(p: Product) -> bool:
                hay = [x.lower() for x in (p.tags or [])] + [x.lower() for x in p.personalization_tags]
                return any(w in h for w in wanted for h in hay)
            out = [p for p in out if _has_any_tag(p)]

    return out


def build_facets(all_products: Iterable[Product], params: FilterParams) -> list[CatalogFacetGroup]:
    products = list(all_products)
    vertical_slice = apply_product_filters(products, params, FilterSkip(vertical=True))
    delivery_slice = apply_product_filters(products, params, FilterSkip(free_delivery=True))
    full_slice = apply_product_filters(products, params)

    def _count(slice_: list[Product], pred) -> int:
        return sum(1 for p in slice_ if pred(p))

    # Department facet — values driven by the actual `p.department` data, not
    # by a hardcoded enum. `_vertical()` returns the lowercased department
    # slug; we sort the resulting buckets by count descending, then alphabetical
    # for deterministic pill ordering. Departments with fewer than HIDE_BELOW
    # items are omitted from the pill bar (they're still reachable via the
    # category dropdown) — this prevents singleton "Fitness" / "Lighting"
    # pills from cluttering the UX.
    HIDE_BELOW = 3
    dept_counts = Counter(_vertical(p) for p in vertical_slice)
    sorted_depts = sorted(
        ((slug, n) for slug, n in dept_counts.items() if n >= HIDE_BELOW),
        key=lambda kv: (-kv[1], kv[0]),
    )

    def _label(slug: str) -> str:
        # "home living" → "Home Living"; preserves multi-word titles.
        return " ".join(part.capitalize() for part in slug.replace("-", " ").split())

    return [
        CatalogFacetGroup(
            id="vertical",
            label="Department",
            facetType="multi",
            values=[
                CatalogFacetValue(
                    value=slug,
                    label=_label(slug),
                    count=count,
                )
                for slug, count in sorted_depts
            ],
        ),
        CatalogFacetGroup(
            id="freeDelivery",
            label="Delivery",
            facetType="boolean",
            values=[
                CatalogFacetValue(
                    value="true",
                    label="Free delivery",
                    count=_count(delivery_slice, lambda p: p.free_delivery is True),
                )
            ],
        ),
        CatalogFacetGroup(
            id="price",
            label="Price",
            facetType="range",
            min=min((p.price for p in full_slice), default=0),
            max=max((p.price for p in full_slice), default=0),
        ),
    ]


def _sort(products: list[Product], sort: SortOrder) -> list[Product]:
    if sort == "price-asc":
        return sorted(products, key=lambda p: p.price)
    if sort == "price-desc":
        return sorted(products, key=lambda p: p.price, reverse=True)
    if sort == "rating":
        return sorted(products, key=lambda p: p.rating, reverse=True)
    return products  # 'featured' = catalog order (no sort)


def filter_products_response(
    all_products: Iterable[Product],
    params: FilterParams,
    sort: SortOrder = "featured",
    page: int = 1,
    page_size: int = 12,
    personalized: bool = False,
) -> ProductListResponse:
    page = max(1, page)
    page_size = min(48, max(1, page_size))

    filtered = apply_product_filters(all_products, params)
    sorted_ = _sort(filtered, sort)

    total = len(sorted_)
    start = (page - 1) * page_size
    items = sorted_[start : start + page_size]

    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        pageSize=page_size,
        personalized=personalized,
    )
