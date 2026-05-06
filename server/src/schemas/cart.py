"""Pydantic models for cart + wishlist endpoints.

These shapes are backend-defined — `apps/web/src/shared/api/contracts.ts`
doesn't have a Cart shape today (the frontend uses Zustand client-side).
Frontend wire-up is out of scope for this milestone.

Each line is enriched with light product metadata (slug, name, image,
unitPrice) so a single GET /me/cart renders the cart view without N+1
catalog lookups on the client.
"""

from pydantic import BaseModel, ConfigDict, Field


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class CartItem(_CamelModel):
    product_id: str = Field(alias="productId")
    slug: str
    name: str
    image: str
    unit_price: float = Field(alias="unitPrice")
    quantity: int
    selected_options: dict[str, str] | None = Field(default=None, alias="selectedOptions")
    added_at: str = Field(alias="addedAt")


class CartResponse(_CamelModel):
    items: list[CartItem]
    item_count: int = Field(alias="itemCount")
    subtotal: float
    updated_at: str | None = Field(default=None, alias="updatedAt")


class AddCartItemBody(_CamelModel):
    product_id: str = Field(alias="productId")
    quantity: int = Field(default=1, gt=0)
    selected_options: dict[str, str] | None = Field(default=None, alias="selectedOptions")


class PatchCartItemBody(_CamelModel):
    quantity: int | None = Field(default=None, gt=0)
    selected_options: dict[str, str] | None = Field(default=None, alias="selectedOptions")


class WishlistItem(_CamelModel):
    product_id: str = Field(alias="productId")
    slug: str
    name: str
    image: str
    unit_price: float = Field(alias="unitPrice")
    added_at: str = Field(alias="addedAt")


class WishlistResponse(_CamelModel):
    items: list[WishlistItem]


class AddWishlistItemBody(_CamelModel):
    product_id: str = Field(alias="productId")
