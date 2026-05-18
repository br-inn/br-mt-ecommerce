"""Pydantic schemas — Unmatched Offers API.

Alineado con `app/db/models/unmatched_offer.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class UnmatchedOfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    marketplace: str
    external_id: str
    title: str
    brand: str | None
    price_aed: Decimal | None
    delivery_text: str | None
    specs_jsonb: dict
    image_url: str | None
    source_url: str | None
    source_sku: str | None
    match_attempts: int
    matched_at: datetime | None
    scraped_at: datetime
    created_at: datetime

    @computed_field
    @property
    def status(self) -> str:
        if self.matched_at is not None:
            return "matched"
        if self.match_attempts >= 3:
            return "exhausted"
        return "pending"

    @computed_field
    @property
    def has_embedding(self) -> bool:
        # `embedding` is a Vector field — not serialized in this schema.
        # We rely on the ORM instance having the attribute populated.
        # Pydantic from_attributes will NOT include `embedding` (not declared here),
        # so we access it via __pydantic_extra__ fallback or model_fields_set.
        # The safest approach: check the raw ORM object via model's __dict__.
        # Since pydantic doesn't expose undeclared attrs, we use the _embedding
        # sentinel set by the validator below. For now return False as safe default —
        # the route populates this properly via _check_embedding helper.
        return False


class UnmatchedOfferResponseWithEmbedding(UnmatchedOfferResponse):
    """Internal variant used by the route to carry has_embedding flag."""

    _embedding_present: bool = False

    @computed_field
    @property
    def has_embedding(self) -> bool:  # type: ignore[override]
        return self._embedding_present

    @classmethod
    def from_orm_with_embedding(cls, obj: object) -> "UnmatchedOfferResponseWithEmbedding":
        instance = cls.model_validate(obj)
        # Access the ORM-level attribute directly
        embedding_val = getattr(obj, "embedding", None)
        object.__setattr__(instance, "_embedding_present", embedding_val is not None)
        return instance


class UnmatchedOffersStats(BaseModel):
    """Estadísticas de estado del pool de unmatched offers."""

    model_config = ConfigDict(extra="forbid")

    total_pending: int
    total_matched: int
    total_exhausted: int
    matched_last_24h: int
    scraped_last_7d: int
