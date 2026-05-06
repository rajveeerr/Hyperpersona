"""Customer profile service.

Reads and writes a single Dynamo row per customer (PK=CUSTOMER#{id},
SK=PROFILE). Addresses live on the profile row and are read-only at the
API level (seeded once via scripts/seed_demo_customer.py).

For customers without a seeded profile (anyone who registered through
`POST /register` rather than the demo seeder), `get_profile` lazily
materializes a starter profile so the FE doesn't 404 on first load.

`get_explanations` returns canned strings — the recommendations engine
that would derive these dynamically is out of scope for this milestone.
"""

from __future__ import annotations

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


def _default_profile(customer_id: str) -> dict:
    """Starter profile for a customer that has never been seeded.

    Empty preference / interest / signal lists let the FE render the
    profile lab without 404ing; rails will fall back to generic ranking
    until events accumulate.
    """
    short_id = customer_id.split("-", 1)[0] if "-" in customer_id else customer_id
    return {
        "customerId": customer_id,
        "name": f"Shopper {short_id[:6]}",
        "segment": "New shopper",
        "topCategories": [],
        "explicitPreferences": [],
        "inferredInterests": [],
        "recentSignals": [],
        "lastUpdated": utc_now_iso(),
        "addresses": [],
    }


class ProfileService:
    def __init__(self, dynamo: DynamoClient) -> None:
        self._dynamo = dynamo

    def _load_or_init(self, customer_id: str) -> dict:
        row = self._dynamo.profile_get(customer_id)
        if row:
            return _strip_dynamo_keys(row)
        starter = _default_profile(customer_id)
        self._dynamo.profile_put(customer_id, starter)
        return starter

    def get_profile(self, customer_id: str) -> ProfileSummary:
        return ProfileSummary.model_validate(self._load_or_init(customer_id))

    def update_preferences(
        self,
        customer_id: str,
        body: UpdatePreferencesBody,
    ) -> ProfileSummary:
        merged = self._load_or_init(customer_id)
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
