"""Pydantic models for the catalog + search endpoints.

Mirrors the frontend contracts in apps/web/src/shared/api/contracts.ts.
Responses use camelCase keys (matching the frontend) by way of explicit
Field aliases — that lets Pydantic accept snake_case from Python while
still serializing camelCase to the wire.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProductVertical = Literal["apparel", "furniture", "electronics", "general"]
InventoryStatus = Literal["in-stock", "low-stock", "backorder"]
SortOrder = Literal["featured", "price-asc", "price-desc", "rating"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ProductVariantOption(_CamelModel):
    id: str
    label: str


class ProductDimensions(_CamelModel):
    display: str | None = None
    length_cm: float | None = Field(default=None, alias="lengthCm")
    width_cm: float | None = Field(default=None, alias="widthCm")
    height_cm: float | None = Field(default=None, alias="heightCm")
    weight_g: float | None = Field(default=None, alias="weightG")


class ViewerProductReview(_CamelModel):
    id: str
    rating: int
    title: str | None = None
    body: str
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class Category(_CamelModel):
    id: str
    slug: str
    name: str
    description: str
    hero: str


class Product(_CamelModel):
    id: str
    slug: str
    name: str
    brand: str
    category: str
    price: float
    compare_at: float | None = Field(default=None, alias="compareAt")
    rating: float
    review_count: int = Field(alias="reviewCount")
    image: str
    description: str
    features: list[str]
    badges: list[str]
    inventory_status: InventoryStatus = Field(alias="inventoryStatus")
    personalization_tags: list[str] = Field(alias="personalizationTags")
    viewer_review: ViewerProductReview | None = Field(default=None, alias="viewerReview")
    vertical: ProductVertical | None = None
    free_delivery: bool | None = Field(default=None, alias="freeDelivery")
    images: list[str] | None = None
    long_description: str | None = Field(default=None, alias="longDescription")
    dimensions: ProductDimensions | None = None
    department: str | None = None
    specification: list[str] | None = None
    date_first_available: str | None = Field(default=None, alias="dateFirstAvailable")
    tags: list[str] | None = None
    color_options: list[ProductVariantOption] | None = Field(default=None, alias="colorOptions")
    size_options: list[ProductVariantOption] | None = Field(default=None, alias="sizeOptions")
    storage_options: list[ProductVariantOption] | None = Field(default=None, alias="storageOptions")


FacetType = Literal["boolean", "single", "multi", "range"]


class CatalogFacetValue(_CamelModel):
    value: str
    label: str
    count: int


class CatalogFacetGroup(_CamelModel):
    id: str
    label: str
    facet_type: FacetType = Field(alias="facetType")
    values: list[CatalogFacetValue] | None = None
    min: float | None = None
    max: float | None = None


class ProductListResponse(_CamelModel):
    items: list[Product]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    personalized: bool
    facets: list[CatalogFacetGroup] | None = None
