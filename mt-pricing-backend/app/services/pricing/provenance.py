"""Provenance + audit helpers for Channel Pricing mutations (F1)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository


def stamp(
    values: dict[str, Any],
    *,
    actor_id: UUID | None,
    source_op: str = "manual",
    source_ref: str | None = None,
    observed_at: datetime | None = None,
    updated_field: str = "updated_by",
) -> dict[str, Any]:
    """Return `values` augmented with provenance fields for an UPDATE/upsert."""
    out = dict(values)
    out[updated_field] = actor_id
    out["source_op"] = source_op
    out["observed_at"] = observed_at or datetime.now(UTC)
    if source_ref is not None:
        out["source_ref"] = source_ref
    return out


async def emit_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: UUID | None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    """Write one audit_events row (hash-chained) reusing AuditRepository."""
    await AuditRepository(session).record(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_role=None if actor_id else "system",
        before=before,
        after=after,
        reason=reason,
    )


async def record_observation(
    session: AsyncSession,
    *,
    source_op: str,
    target_table: str,
    target_field: str,
    value: Any,
    sku: str | None = None,
    channel_id: UUID | None = None,
    source_ref: str | None = None,
    observed_at: datetime | None = None,
) -> None:
    """Append a field-level observation to source_observations."""
    from app.db.models.provenance import SourceObservation

    is_num = isinstance(value, (int, float, Decimal))
    session.add(
        SourceObservation(
            source_op=source_op,
            target_table=target_table,
            target_field=target_field,
            sku=sku,
            channel_id=channel_id,
            value_numeric=Decimal(str(value)) if is_num else None,
            value_text=None if is_num else (str(value) if value is not None else None),
            source_ref=source_ref,
            observed_at=observed_at or datetime.now(UTC),
        )
    )
    await session.flush()
