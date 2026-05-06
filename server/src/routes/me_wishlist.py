"""Wishlist endpoints — GET / POST / DELETE under /me/wishlist."""

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.cart import AddWishlistItemBody
from ..services.wishlist import WishlistService

router = APIRouter()


def _service(request: Request) -> WishlistService:
    return WishlistService(dynamo=dynamo, snapshot=request.app.state.catalog)


def _serialize(model) -> JSONResponse:
    payload = model.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/me/wishlist")
def get_wishlist(
    request: Request,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).get_wishlist(customer_id))


@router.post("/me/wishlist/items")
def add_wishlist_item(
    request: Request,
    body: AddWishlistItemBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).add_item(customer_id, body))


@router.delete("/me/wishlist/items/{product_id}")
def delete_wishlist_item(
    request: Request,
    product_id: str,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).delete_item(customer_id, product_id))
