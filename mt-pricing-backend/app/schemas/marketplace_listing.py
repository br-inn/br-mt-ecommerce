"""Pydantic schemas for product_marketplace_listings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Marketplace = Literal["amazon_uae", "noon_uae", "shopify_storefront"]
ListingStatus = Literal["draft", "ready", "published", "paused"]


class MarketplaceListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_sku: str
    marketplace: str
    status: str
    listing_title: str | None
    listing_description: str | None
    bullet_points: list[str]
    search_keywords: str | None
    extra: dict[str, Any]
    ai_generated_at: datetime | None
    ai_model: str | None
    created_at: datetime
    updated_at: datetime


class MarketplaceListingUpsert(BaseModel):
    status: ListingStatus = "draft"
    listing_title: str | None = Field(None, max_length=200)
    listing_description: str | None = Field(None, max_length=2000)
    bullet_points: list[str] = Field(default_factory=list, max_length=5)
    search_keywords: str | None = Field(None, max_length=500)
    extra: dict[str, Any] = Field(default_factory=dict)


class AmazonFieldError(BaseModel):
    field: str
    code: str
    message: str


class AmazonListingValidation(BaseModel):
    sku: str
    is_ready: bool
    errors: list[AmazonFieldError]
    warnings: list[AmazonFieldError]


class AmazonValidationReport(BaseModel):
    total_skus: int
    ready_count: int
    draft_count: int
    error_count: int
    listings: list[AmazonListingValidation]


class GenerateListingRequest(BaseModel):
    overwrite: bool = Field(
        default=False,
        description="If True, regenerate even if content already exists.",
    )
