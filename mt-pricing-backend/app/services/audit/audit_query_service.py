"""Audit query service — multi-entity filters para tab Auditoría (US-1A-07-03).

Sprint 4 — backend del UI tab Auditoría en SKU detail. El service consume
``AuditRepository`` ya existente y permite filtros que NO existen en el
endpoint legacy `app/api/routes/audit.py`:

- ``entity_types``: lista de entidades (e.g. ['products','costs','prices',
  'product_translations']) — el endpoint legacy sólo aceptaba uno.
- ``entity_ids``: lista de ids — útil cuando un SKU tiene cost_id, price_id
  diferentes pero queremos el timeline unificado.
- ``related_sku``: fan-out real por SKU. Genera un OR de cláusulas:
    - products:             entity_type='product'             AND entity_id = sku
    - costs:                entity_type='cost'                AND entity_id IN (SELECT id::text FROM costs WHERE sku = :sku)
    - prices:               entity_type='price'               AND entity_id IN (SELECT id::text FROM prices WHERE product_sku = :sku)
    - product_translations: entity_type='product_translation' AND entity_id LIKE '{sku}:%'
  El cast id::text es necesario porque audit_events.entity_id es TEXT y las
  PKs son UUID. fx_rates no tiene FK a SKU (son tasas globales) y se excluye
  del fan-out automático (puede añadirse vía entity_types si se desea).
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

from sqlalchemy import and_, cast, or_, select, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.models.cost import Cost
from app.db.models.pricing import Price
from app.db.models.product import ProductTranslation
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


# Tipos de entidad que participan en el fan-out por SKU.
# Cada uno requiere lógica diferente según cómo almacena el entity_id.
_PRODUCT_ENTITY_TYPES: tuple[str, ...] = ("products", "product")
_COST_ENTITY_TYPES: tuple[str, ...] = ("costs", "cost")
_PRICE_ENTITY_TYPES: tuple[str, ...] = ("prices", "price")
_TRANSLATION_ENTITY_TYPES: tuple[str, ...] = ("product_translations", "product_translation")


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
    def _build_related_sku_clause(self, sku: str) -> Any:
        """Genera la cláusula OR de fan-out para todos los eventos de un SKU.

        Mapping real de entity_id por entidad:
        - product:              entity_id = sku (TEXT directo)
        - cost:                 entity_id = str(cost.id) → subquery costs WHERE sku = :sku
        - price:                entity_id = str(price.id) → subquery prices WHERE product_sku = :sku
        - product_translation:  entity_id = f"{sku}:{lang}" → LIKE '{sku}:%'
        """
        # Products: entity_id IS el SKU directamente
        product_clause = and_(
            AuditEvent.entity_type.in_(_PRODUCT_ENTITY_TYPES),
            AuditEvent.entity_id == sku,
        )

        # Costs: entity_id es UUID del cost → buscar costos del SKU
        cost_ids_subq = select(cast(Cost.id, Text)).where(Cost.sku == sku).scalar_subquery()
        cost_clause = and_(
            AuditEvent.entity_type.in_(_COST_ENTITY_TYPES),
            AuditEvent.entity_id.in_(cost_ids_subq),
        )

        # Prices: entity_id es UUID del price → buscar precios del SKU
        price_ids_subq = select(cast(Price.id, Text)).where(Price.product_sku == sku).scalar_subquery()
        price_clause = and_(
            AuditEvent.entity_type.in_(_PRICE_ENTITY_TYPES),
            AuditEvent.entity_id.in_(price_ids_subq),
        )

        # Product translations: entity_id = "{sku}:{lang}" → LIKE match
        translation_clause = and_(
            AuditEvent.entity_type.in_(_TRANSLATION_ENTITY_TYPES),
            AuditEvent.entity_id.like(f"{sku}:%"),
        )

        return or_(product_clause, cost_clause, price_clause, translation_clause)

    def _build_conditions(self, filters: AuditQueryFilters) -> list[Any]:
        conditions: list[Any] = []

        if filters.related_sku:
            # Fan-out real: OR de todas las entidades enlazadas al SKU.
            # El fan-out resuelve correctamente qué entity_id corresponde a cada
            # tipo de entidad (UUID para costs/prices, SKU para products,
            # SKU:lang para translations). Los entity_types/entity_ids opcionales
            # se añaden como filtros adicionales AND para acotar el resultado:
            # e.g. related_sku=MT-V-038 AND entity_type IN ('costs','prices').
            sku_clause = self._build_related_sku_clause(filters.related_sku)
            conditions.append(sku_clause)
            # Narrowing adicional: si se pasan entity_types, acotar dentro del fan-out.
            if filters.entity_types:
                conditions.append(AuditEvent.entity_type.in_(filters.entity_types))
            if filters.entity_ids:
                conditions.append(AuditEvent.entity_id.in_(filters.entity_ids))
        else:
            # Filtros directos sin fan-out (entity_types e ids AND entre sí).
            if filters.entity_types:
                conditions.append(AuditEvent.entity_type.in_(filters.entity_types))
            if filters.entity_ids:
                conditions.append(AuditEvent.entity_id.in_(filters.entity_ids))

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
