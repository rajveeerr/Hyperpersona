"""Customer profile service.

Reads and writes a single Dynamo row per customer (PK=CUSTOMER#{id},
SK=PROFILE). Addresses live on the profile row and are read-only at the
API level (seeded once via scripts/seed_demo_customer.py).

`get_explanations` returns canned strings — the recommendations engine
that would derive these dynamically is out of scope for this milestone.
"""

from __future__ import annotations

from fastapi import HTTPException

from shared.dynamo import DynamoClient
from shared.schemas import utc_now_iso

from ..schemas.profile import (
    ExplanationRecord,
    ProfileSummary,
    UpdatePreferencesBody,
)


_STATIC_EXPLANATIONS = ExplanationRecord(
    search=[
        "Outdoor affinity boosted weatherproof products.",
        "Recent searches increased trail accessory relevance.",
    ],
    recommendations=[
        "Home rail uses recent browsing, category affinity, and price comfort zone.",
        "Related items prioritize complementary gear from the same use case.",
    ],
    profileSignals=[
        "Explicit budget preference keeps premium overages limited.",
        "Recent activity favors weather-ready and trail gear.",
    ],
)


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


class ProfileService:
    def __init__(self, dynamo: DynamoClient) -> None:
        self._dynamo = dynamo

    def get_profile(self, customer_id: str) -> ProfileSummary:
        row = self._dynamo.profile_get(customer_id)
        if not row:
            raise HTTPException(status_code=404, detail="profile not found")
        return ProfileSummary.model_validate(_strip_dynamo_keys(row))

    def update_preferences(
        self,
        customer_id: str,
        body: UpdatePreferencesBody,
    ) -> ProfileSummary:
        existing = self._dynamo.profile_get(customer_id)
        if not existing:
            raise HTTPException(status_code=404, detail="profile not found")

        merged = _strip_dynamo_keys(existing)
        merged["explicitPreferences"] = [p.model_dump(by_alias=True) for p in body.explicit_preferences]
        merged["lastUpdated"] = utc_now_iso()

        # profile_put expects camelCase keys (matches what we read back).
        self._dynamo.profile_put(customer_id, merged)
        return ProfileSummary.model_validate(merged)

    def get_explanations(self, customer_id: str) -> ExplanationRecord:
        # `customer_id` accepted to keep the dependency signature uniform
        # with future personalized variants; currently the strings are
        # static (out of scope to derive dynamically).
        return _STATIC_EXPLANATIONS
