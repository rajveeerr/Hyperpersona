"""Consent endpoints — POST to write/update, GET to read."""

from fastapi import APIRouter, Depends, HTTPException

from shared.schemas import ConsentRecord, ConsentUpsertRequest

from ..deps import dynamo as _dynamo
from ..middleware.auth import current_customer_id


router = APIRouter()


def _clean(record: dict) -> dict:
    record.pop("PK", None)
    record.pop("SK", None)
    if isinstance(record.get("scopes"), set):
        record["scopes"] = sorted(record["scopes"])
    return record


@router.post("/consent")
def upsert_consent(
    req: ConsentUpsertRequest,
    customer_id: str = Depends(current_customer_id),
) -> dict:
    consent = ConsentRecord(
        customer_id=customer_id,
        scopes=req.scopes,
        data_retention_days=req.data_retention_days,
    )
    _dynamo.put_consent(consent.model_dump())
    return {
        "customer_id": consent.customer_id,
        "scopes": sorted(consent.scopes),
        "data_retention_days": consent.data_retention_days,
    }


@router.get("/consent")
def get_consent(customer_id: str = Depends(current_customer_id)) -> dict:
    record = _dynamo.get_consent(customer_id)
    if not record:
        raise HTTPException(status_code=404, detail="consent record not found")
    return _clean(record)
