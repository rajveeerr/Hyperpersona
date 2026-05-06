"""Cart endpoints — GET / POST / PATCH / DELETE under /me/cart."""

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.cart import AddCartItemBody, PatchCartItemBody
from ..services.cart import CartService

router = APIRouter()


def _service(request: Request) -> CartService:
    return CartService(dynamo=dynamo, snapshot=request.app.state.catalog)


def _serialize(model) -> JSONResponse:
    payload = model.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/me/cart")
def get_cart(
    request: Request,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).get_cart(customer_id))


@router.post("/me/cart/items")
def add_cart_item(
    request: Request,
    body: AddCartItemBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).add_item(customer_id, body))


@router.patch("/me/cart/items/{product_id}")
def patch_cart_item(
    request: Request,
    product_id: str,
    body: PatchCartItemBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).patch_item(customer_id, product_id, body))


@router.delete("/me/cart/items/{product_id}")
def delete_cart_item(
    request: Request,
    product_id: str,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service(request).delete_item(customer_id, product_id))
