"""Order history — GET /me/orders, paginated."""

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..services.orders import OrdersService

router = APIRouter()
_service = OrdersService(dynamo=dynamo)


@router.get("/me/orders")
def list_orders(
    page: int = 1,
    pageSize: int = Query(default=10, ge=1, le=50),
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    response = _service.list_orders(customer_id, page, pageSize)
    payload = response.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))
