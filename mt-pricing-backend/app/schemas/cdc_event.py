"""Schemas para CDC (Change Data Capture) events — Supabase Realtime → Celery."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CdcProductEvent(BaseModel):
    """Payload recibido del webhook Supabase Realtime CDC."""

    table: str
    operation: str  # INSERT / UPDATE / DELETE
    record_id: str
    payload: dict[str, Any] = {}
    received_at: datetime | None = None

    model_config = {"extra": "ignore"}
