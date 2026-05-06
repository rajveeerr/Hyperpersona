"""Pydantic models for the customer profile endpoint.

Mirrors apps/web/src/shared/api/contracts.ts:201-291. Per project scope,
addresses are read-only on GET /me/profile (seeded; no PATCH /me/addresses).
"""

from pydantic import BaseModel, ConfigDict, Field


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ExplicitPreference(_CamelModel):
    key: str
    label: str
    value: str


class InferredInterest(_CamelModel):
    id: str
    label: str
    confidence: float
    source: str


class DeliveryAddress(_CamelModel):
    id: str
    label: str
    line1: str
    line2: str | None = None
    city: str
    region: str | None = None
    postal_code: str = Field(alias="postalCode")
    country: str
    is_default: bool | None = Field(default=None, alias="isDefault")


class ProfileSummary(_CamelModel):
    customer_id: str = Field(alias="customerId")
    name: str
    segment: str
    top_categories: list[str] = Field(alias="topCategories")
    explicit_preferences: list[ExplicitPreference] = Field(alias="explicitPreferences")
    inferred_interests: list[InferredInterest] = Field(alias="inferredInterests")
    recent_signals: list[str] = Field(alias="recentSignals")
    last_updated: str = Field(alias="lastUpdated")
    addresses: list[DeliveryAddress] = Field(default_factory=list)


class UpdatePreferencesBody(_CamelModel):
    explicit_preferences: list[ExplicitPreference] = Field(alias="explicitPreferences")


class ExplanationRecord(_CamelModel):
    search: list[str]
    recommendations: list[str]
    profile_signals: list[str] = Field(alias="profileSignals")
