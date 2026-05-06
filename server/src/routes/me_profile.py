"""Customer profile endpoints — GET /me/profile, PATCH /me/preferences,
GET /me/explanations.

All three resolve `customer_id` via the existing JWTAuthMiddleware →
current_customer_id dependency.
"""

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..deps import dynamo
from ..middleware.auth import current_customer_id
from ..schemas.profile import UpdatePreferencesBody
from ..services.profile import ProfileService

router = APIRouter()
_service = ProfileService(dynamo=dynamo)


def _serialize(model) -> JSONResponse:
    payload = model.model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(content=jsonable_encoder(payload))


@router.get("/me/profile")
def get_profile(customer_id: str = Depends(current_customer_id)) -> JSONResponse:
    return _serialize(_service.get_profile(customer_id))


@router.patch("/me/preferences")
def update_preferences(
    body: UpdatePreferencesBody,
    customer_id: str = Depends(current_customer_id),
) -> JSONResponse:
    return _serialize(_service.update_preferences(customer_id, body))


@router.get("/me/explanations")
def get_explanations(customer_id: str = Depends(current_customer_id)) -> JSONResponse:
    return _serialize(_service.get_explanations(customer_id))
