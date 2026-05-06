"""POST /checkout — server-side total recompute, write order, clear cart."""

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.orders import CheckoutInput
from ..services.checkout import CheckoutService

router = APIRouter()


def _service(request: Request) -> CheckoutService:
    return CheckoutService(dynamo=dynamo, snapshot=request.app.state.catalog)


@router.post("/checkout")
def checkout(
    request: Request,
    body: CheckoutInput,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    response = _service(request).checkout(customer_id, body)
    payload = response.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))
