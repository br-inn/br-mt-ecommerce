"""CdcDispatcher — consume cdc_events outbox y propaga al graph store.

Flujo:

1. ``fetch_pending(batch_size)`` lee N rows ``status='pending'`` ORDER BY id ASC.
2. Por cada row:
    a. ``SchemaMapper.map_event(...)`` produce ``(nodes, edges)``.
    b. Para ``action='delete'`` se llama ``delete_subgraph`` con la etiqueta
       canónica del entity_type.
    c. Para ``insert``/``update`` se invocan ``merge_node`` y ``merge_edge``.
3. Marca el row ``processed`` (con ``processed_at``) o ``failed`` (incrementa
   ``attempts`` y guarda ``last_error``). Tras 3 fallos pasa a ``dead_letter``.

Idempotencia:
- El graph store implementa MERGE → reprocesar el mismo evento es seguro.
- Los rows ``processed`` no se vuelven a leer (filtro ``status='pending'``).
- ``replay()`` resetea rows a ``pending`` para forzar reprocesado (admin only).

NO maneja:
- LISTEN/NOTIFY directo (el polling lo dispara la task Celery — Fase 1).
  En Fase 2+ se reemplaza por Supabase Realtime → Redis (ADR-041).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cdc_event import CdcEvent
from app.services.graphrag.ports import GraphStorePort
from app.services.graphrag.schema_mapper import SchemaMapper

logger = structlog.get_logger(__name__)


MAX_ATTEMPTS_BEFORE_DEAD_LETTER = 3


class CdcDispatcher:
    """Procesa rows de ``cdc_events`` contra un ``GraphStorePort`` inyectado."""

    def __init__(
        self,
        session: AsyncSession,
        graph_store: GraphStorePort,
        *,
        mapper: type[SchemaMapper] = SchemaMapper,
    ) -> None:
        self.session = session
        self.graph = graph_store
        self.mapper = mapper

    # ----------------------------------------------------------------- queries
    async def fetch_pending(self, batch_size: int = 100) -> list[CdcEvent]:
        stmt = (
            select(CdcEvent)
            .where(CdcEvent.status == "pending")
            .order_by(CdcEvent.id.asc())
            .limit(batch_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ----------------------------------------------------------------- core
    async def process_one(self, event: CdcEvent) -> dict[str, Any]:
        """Procesa un evento. Devuelve dict con outcome y conteos."""
        try:
            self._dispatch_to_graph(event)
        except Exception as exc:
            event.attempts = (event.attempts or 0) + 1
            event.last_error = f"{type(exc).__name__}: {exc}"
            if event.attempts >= MAX_ATTEMPTS_BEFORE_DEAD_LETTER:
                event.status = "dead_letter"
            else:
                event.status = "failed"
            logger.warning(
                "graphrag.cdc.process_one.failed",
                event_id=event.id,
                attempts=event.attempts,
                status=event.status,
                error=event.last_error,
            )
            return {
                "event_id": event.id,
                "outcome": event.status,
                "error": event.last_error,
            }
        event.status = "processed"
        event.processed_at = datetime.now(tz=UTC)
        event.last_error = None
        return {
            "event_id": event.id,
            "outcome": "processed",
        }

    def _dispatch_to_graph(self, event: CdcEvent) -> None:
        """Aplica las mutaciones derivadas del evento al graph store."""
        if event.action == "delete":
            label = self.mapper.primary_label(event.entity_type)
            if label is None:
                logger.warning(
                    "graphrag.cdc.delete.unsupported_entity",
                    entity_type=event.entity_type,
                )
                return
            self.graph.delete_subgraph(label, event.entity_id)
            return

        nodes, edges = self.mapper.map_event(
            entity_type=event.entity_type,
            action=event.action,
            payload=dict(event.payload_jsonb or {}),
        )
        for node in nodes:
            self.graph.merge_node(node)
        for edge in edges:
            self.graph.merge_edge(edge)

    # ----------------------------------------------------------------- batch
    async def process_batch(self, batch_size: int = 100) -> dict[str, Any]:
        events = await self.fetch_pending(batch_size=batch_size)
        outcomes: list[dict[str, Any]] = []
        for event in events:
            outcome = await self.process_one(event)
            outcomes.append(outcome)
        # `flush` para persistir cambios de status — el commit lo hace
        # `get_db_session` o el caller (Celery task wrapping).
        await self.session.flush()
        processed = sum(1 for o in outcomes if o["outcome"] == "processed")
        failed = sum(1 for o in outcomes if o["outcome"] == "failed")
        dead_lettered = sum(1 for o in outcomes if o["outcome"] == "dead_letter")
        return {
            "scanned": len(events),
            "processed": processed,
            "failed": failed,
            "dead_lettered": dead_lettered,
            "outcomes": outcomes,
        }

    # ----------------------------------------------------------------- replay
    async def replay(
        self,
        *,
        entity_type: str | None = None,
        only_dead_letter: bool = False,
    ) -> int:
        """Resetea rows a ``pending`` para forzar reprocesado.

        - ``only_dead_letter=True`` → sólo afecta a rows en ``dead_letter``.
        - ``entity_type`` opcional → filtra por tipo (re-cargar solo
          productos, por ejemplo).
        Devuelve el número de rows tocados.
        """
        stmt = update(CdcEvent).values(
            status="pending",
            attempts=0,
            last_error=None,
            processed_at=None,
        )
        if only_dead_letter:
            stmt = stmt.where(CdcEvent.status == "dead_letter")
        else:
            stmt = stmt.where(CdcEvent.status.in_(["processed", "failed", "dead_letter"]))
        if entity_type is not None:
            stmt = stmt.where(CdcEvent.entity_type == entity_type)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)


__all__ = ["MAX_ATTEMPTS_BEFORE_DEAD_LETTER", "CdcDispatcher"]
