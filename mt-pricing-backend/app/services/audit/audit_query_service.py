"""Audit query service — multi-entity filters para tab Auditoría (US-1A-07-03).

Sprint 4 — backend del UI tab Auditoría en SKU detail. El service consume
``AuditRepository`` ya existente y permite filtros que NO existen en el
endpoint legacy `app/api/routes/audit.py`:

- ``entity_types``: lista de entidades (e.g. ['products','costs','prices',
  'product_translations']) — el endpoint legacy sólo aceptaba uno.
- ``entity_ids``: lista de ids — útil cuando un SKU tiene cost_id, price_id
  diferentes pero queremos el timeline unificado.
- ``related_sku``: shortcut que infla la query a `(entity='products' AND
  entity_id=sku) OR (entity IN ('costs','prices','product_translations') AND
  payload contiene sku)`. Implementación pragmática: por ahora joinea solo
  por entity_id directo, asumiendo que `costs`/`prices` registran el SKU
  como `entity_id`. Si el modelo cambia → simple ajuste en este servicio sin
  romper el contrato API.
- ``actions``: lista de acciones (e.g. ['price.proposed','price.approved']).
- ``actor_email``: search by partial email.

Diseño:
- Stateless por request, vía ``async with AsyncSession``.
- Pure read — NO emite audit events propios (sería recursivo).
- Output ``AuditQueryResult`` (dict-like) para facilitar serialización
  Pydantic en el router sin acoplar a ORM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.models.user import User

__all__ = [
    "AuditQueryFilters",
    "AuditQueryResult",
    "AuditQueryService",
]


@dataclass(frozen=True)
class AuditQueryFilters:
    """Filtros multi-entidad para queries del tab Auditoría.

    Todos los campos son opcionales — sin ningún filtro la query devuelve
    el timeline completo (paginado).
    """

    entity_types: tuple[str, ...] | None = None
    entity_ids: tuple[str, ...] | None = None
    related_sku: str | None = None
    actor_id: UUID | None = None
    actor_email: str | None = None
    actions: tuple[str, ...] | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass
class AuditQueryResultRow:
    """Una fila de salida — JSON-friendly."""

    id: str
    event_at: datetime
    entity_type: str
    entity_id: str
    action: str
    actor_id: UUID | None
    actor_email: str | None
    actor_full_name: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    payload_diff: dict[str, Any]
    reason: str | None


@dataclass
class AuditQueryResult:
    items: list[AuditQueryResultRow] = field(default_factory=list)
    next_cursor: tuple[datetime, int] | None = None


_RELATED_ENTITY_TYPES_FOR_SKU: tuple[str, ...] = (
    "products",
    "product",  # algunos servicios registran singular
    "product_translations",
    "translation",
    "costs",
    "cost",
    "prices",
    "price",
)


class AuditQueryService:
    """Servicio dedicado a las queries multi-entidad."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def query(
        self,
        filters: AuditQueryFilters,
        *,
        cursor: tuple[datetime, int] | None = None,
        limit: int = 50,
    ) -> AuditQueryResult:
        """Ejecuta la query keyset-paginada respetando filters.

        El cursor es la tupla ``(event_at, id)`` del último item devuelto
        (orden DESC por event_at, id).
        """
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200

        stmt = select(AuditEvent, User).join(
            User, User.id == AuditEvent.actor_id, isouter=True
        )

        conditions = self._build_conditions(filters)

        if cursor is not None:
            cursor_at, cursor_id = cursor
            conditions.append(
                or_(
                    AuditEvent.event_at < cursor_at,
                    and_(
                        AuditEvent.event_at == cursor_at,
                        AuditEvent.id < cursor_id,
                    ),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.order_by(
            AuditEvent.event_at.desc(),
            AuditEvent.id.desc(),
        ).limit(limit + 1)

        result = await self.session.execute(stmt)
        rows: list[tuple[AuditEvent, User | None]] = [
            (row[0], row[1]) for row in result.all()
        ]

        next_cursor: tuple[datetime, int] | None = None
        if len(rows) > limit:
            last = rows[limit - 1][0]
            next_cursor = (last.event_at, last.id)
            rows = rows[:limit]

        items: list[AuditQueryResultRow] = []
        for evt, user in rows:
            items.append(
                AuditQueryResultRow(
                    id=str(evt.id),
                    event_at=evt.event_at,
                    entity_type=evt.entity_type,
                    entity_id=evt.entity_id,
                    action=evt.action,
                    actor_id=evt.actor_id,
                    actor_email=(user.email if user is not None else evt.actor_email),
                    actor_full_name=(user.full_name if user is not None else None),
                    before=evt.before,
                    after=evt.after,
                    payload_diff=evt.payload_diff or {},
                    reason=evt.reason,
                )
            )

        return AuditQueryResult(items=items, next_cursor=next_cursor)

    # ---------------------------------------------------------------- helpers
    def _build_conditions(self, filters: AuditQueryFilters) -> list[Any]:
        conditions: list[Any] = []

        # entity_types e ids — combinan con AND si ambos presentes.
        if filters.entity_types:
            conditions.append(AuditEvent.entity_type.in_(filters.entity_types))
        if filters.entity_ids:
            conditions.append(AuditEvent.entity_id.in_(filters.entity_ids))

        if filters.related_sku:
            sku = filters.related_sku
            related_clause = and_(
                AuditEvent.entity_type.in_(_RELATED_ENTITY_TYPES_FOR_SKU),
                AuditEvent.entity_id == sku,
            )
            # Si el caller pasó entity_types/ids además de related_sku, expandimos
            # con OR; la idea es "muestra este SKU + sus dominios relacionados".
            if filters.entity_types or filters.entity_ids:
                # Aux: dejamos el ya-añadido AND como una rama, y or-encadenamos.
                # Removemos los anteriores y reemplazamos por el OR consolidado.
                prev_entity = []
                if filters.entity_types:
                    prev_entity.append(AuditEvent.entity_type.in_(filters.entity_types))
                if filters.entity_ids:
                    prev_entity.append(AuditEvent.entity_id.in_(filters.entity_ids))
                # Dropear los appends anteriores (evita doble filtro)
                conditions = [
                    c
                    for c in conditions
                    if c is not (prev_entity[0] if prev_entity else None)
                ]
                conditions = []  # rebuild clean
                conditions.append(or_(and_(*prev_entity), related_clause))
            else:
                conditions.append(related_clause)

        if filters.actor_id is not None:
            conditions.append(AuditEvent.actor_id == filters.actor_id)
        if filters.actor_email:
            # ilike — partial match.
            conditions.append(AuditEvent.actor_email.ilike(f"%{filters.actor_email}%"))
        if filters.actions:
            conditions.append(AuditEvent.action.in_(filters.actions))
        if filters.since is not None:
            conditions.append(AuditEvent.event_at >= filters.since)
        if filters.until is not None:
            conditions.append(AuditEvent.event_at <= filters.until)

        return conditions
