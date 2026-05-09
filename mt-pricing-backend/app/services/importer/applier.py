"""Applier — aplica diffs en chunks de 1000 rows con savepoints.

Patrón:
- Para cada chunk: ``BEGIN SAVEPOINT chunk_<n>``.
- Procesa cada :class:`RowDiff` (CREATE/UPDATE; ignora NO_CHANGE/SKIP_LOCKED/ERROR).
- Si todo OK → ``RELEASE SAVEPOINT``.
- Si excepción durante el chunk → ``ROLLBACK TO SAVEPOINT`` y registra el
  chunk como fallido; el siguiente chunk continúa.
- Audit event por chunk (resumen) + 1 audit event por row aplicada (consistente
  con el comportamiento del PUT regular).

NO usa ``pg_advisory_lock`` aquí — eso lo manejará la capa Celery cuando llegue
la migración (S3). En S2 el lock es responsabilidad del caller (router serializa
con un lock asyncio en :class:`ImporterService`).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.product import Product
from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.repositories.product import ProductRepository
from app.services.importer.differ import RowAction, RowDiff
from app.services.imports.division_assignment import assign_divisions

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChunkResult:
    chunk_index: int
    start_row: int
    end_row: int
    created: int = 0
    updated: int = 0
    skipped_locked: int = 0
    no_change: int = 0
    errors: int = 0
    failed: bool = False
    failure_reason: str | None = None


@dataclass(slots=True)
class ApplyResult:
    total_rows: int
    chunks: list[ChunkResult] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def created(self) -> int:
        return sum(c.created for c in self.chunks)

    @property
    def updated(self) -> int:
        return sum(c.updated for c in self.chunks)

    @property
    def skipped_locked(self) -> int:
        return sum(c.skipped_locked for c in self.chunks)

    @property
    def no_change(self) -> int:
        return sum(c.no_change for c in self.chunks)

    @property
    def errors(self) -> int:
        return sum(c.errors for c in self.chunks)

    @property
    def failed_chunks(self) -> int:
        return sum(1 for c in self.chunks if c.failed)


def _chunked(
    seq: Sequence[RowDiff], size: int
) -> AsyncIterator[tuple[int, int, int, list[RowDiff]]]:
    """Async generator de tuplas (chunk_idx, start_row, end_row, chunk).

    No tiene awaits dentro — pero lo dejamos como async para encajar con el
    contexto async del caller sin introducir generadores síncronos en hot-path.
    """

    async def _gen() -> AsyncIterator[tuple[int, int, int, list[RowDiff]]]:
        for i in range(0, len(seq), size):
            chunk = list(seq[i : i + size])
            if not chunk:
                continue
            start = chunk[0].row_index
            end = chunk[-1].row_index
            yield i // size, start, end, chunk

    return _gen()


async def _apply_one(
    session: AsyncSession,
    repo: ProductRepository,
    audit: AuditRepository,
    diff: RowDiff,
    actor: User,
    *,
    run_id: str,
    division_codes: list[str] | None = None,
    division_code_cache: dict[str, Any] | None = None,
) -> str:
    """Aplica un :class:`RowDiff` y devuelve la action realizada (string).

    Sólo CREATE/UPDATE producen mutación + audit. SKIP_LOCKED/NO_CHANGE/ERROR
    se cuentan pero no tocan BD ni audit.

    Stage 3 Wave 11: si ``division_codes`` no está vacío, asigna esas
    divisiones al producto upserted (idempotente).
    """
    if diff.action == RowAction.CREATE:
        payload = dict(diff.payload)
        payload["created_by"] = actor.id
        payload["updated_by"] = actor.id
        await repo.create(**payload)
        await audit.record(
            entity_type="product",
            entity_id=diff.sku or "",
            action="product.imported.created",
            actor_id=actor.id,
            actor_email=actor.email,
            after=diff.payload,
            payload_diff={"_import_run_id": run_id},
            reason=f"PIM import run {run_id}",
        )
        if division_codes and diff.sku:
            await assign_divisions(
                session, diff.sku, division_codes,
                code_id_cache=division_code_cache,
            )
        return "created"
    if diff.action == RowAction.UPDATE:
        existing = await repo.get_by_sku(diff.sku)  # type: ignore[arg-type]
        if existing is None:
            # Race condition — alguien lo borró entre preview y apply.
            return "errors"
        # Aplica sólo los campos en el diff filtrado (sin locked).
        for f, change in diff.diff.items():
            setattr(existing, f, change["to"])
        existing.updated_by = actor.id
        existing.updated_at = datetime.now(tz=timezone.utc)
        await session.flush()
        await audit.record(
            entity_type="product",
            entity_id=diff.sku or "",
            action="product.imported.updated",
            actor_id=actor.id,
            actor_email=actor.email,
            payload_diff=diff.diff,
            reason=f"PIM import run {run_id}",
        )
        if division_codes and diff.sku:
            await assign_divisions(
                session, diff.sku, division_codes,
                code_id_cache=division_code_cache,
            )
        return "updated"
    if diff.action == RowAction.SKIP_LOCKED:
        return "skipped_locked"
    if diff.action == RowAction.NO_CHANGE:
        return "no_change"
    return "errors"


async def apply_diffs_chunked(
    session: AsyncSession,
    diffs: Sequence[RowDiff],
    actor: User,
    *,
    run_id: str,
    chunk_size: int = 1000,
    division_codes: list[str] | None = None,
) -> ApplyResult:
    """Aplica el conjunto de diffs en chunks de ``chunk_size``.

    Cada chunk se ejecuta dentro de un savepoint (``session.begin_nested()``).
    Si un chunk falla, se hace rollback del savepoint y el siguiente chunk
    continúa. La transacción exterior debe ser controlada por el caller
    (FastAPI dependency ``get_db_session`` hace commit-on-success).

    Stage 3 Wave 11: ``division_codes`` (override per-call) o
    ``settings.PIM_DEFAULT_DIVISIONS`` (fallback) se asignan a cada
    producto upserted via :func:`assign_divisions` (idempotente).
    """
    repo = ProductRepository(session)
    audit = AuditRepository(session)

    # Stage 3 Wave 11 — resolve division mapping una vez por apply.
    effective_div_codes: list[str] = (
        list(division_codes)
        if division_codes is not None
        else list(settings.PIM_DEFAULT_DIVISIONS or [])
    )
    div_code_cache: dict[str, Any] = {}

    result = ApplyResult(total_rows=len(diffs), started_at=datetime.now(tz=timezone.utc))

    async for chunk_idx, start_row, end_row, chunk in _chunked(diffs, chunk_size):
        chunk_res = ChunkResult(chunk_index=chunk_idx, start_row=start_row, end_row=end_row)
        try:
            async with session.begin_nested() as savepoint:  # noqa: F841
                for d in chunk:
                    try:
                        action = await _apply_one(
                            session, repo, audit, d, actor,
                            run_id=run_id,
                            division_codes=effective_div_codes,
                            division_code_cache=div_code_cache,
                        )
                    except Exception:  # noqa: BLE001 — fila individual no debe matar chunk si controlable
                        logger.exception(
                            "Importer apply: row %s sku=%s failed",
                            d.row_index, d.sku,
                        )
                        chunk_res.errors += 1
                        # Re-raise para hacer rollback del chunk completo (el
                        # tester puede preferir per-row resilience; aquí
                        # priorizamos consistencia transaccional por chunk).
                        raise
                    if action == "created":
                        chunk_res.created += 1
                    elif action == "updated":
                        chunk_res.updated += 1
                    elif action == "skipped_locked":
                        chunk_res.skipped_locked += 1
                    elif action == "no_change":
                        chunk_res.no_change += 1
                    elif action == "errors":
                        chunk_res.errors += 1
        except Exception as exc:  # noqa: BLE001 — chunk-level rollback intencional
            chunk_res.failed = True
            chunk_res.failure_reason = f"{type(exc).__name__}: {exc!s}"
            # El savepoint ya hizo rollback al salir del with por excepción.
            # Audit del chunk fallido.
            try:
                await audit.record(
                    entity_type="import_run_chunk",
                    entity_id=f"{run_id}:{chunk_idx}",
                    action="product.import.chunk_failed",
                    actor_id=actor.id,
                    actor_email=actor.email,
                    payload_diff={
                        "chunk_index": chunk_idx,
                        "start_row": start_row,
                        "end_row": end_row,
                        "reason": chunk_res.failure_reason,
                    },
                    reason=f"PIM import run {run_id} chunk {chunk_idx}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("Importer: failed to audit chunk failure")

        # Audit summary del chunk (siempre — éxito o fallo).
        try:
            await audit.record(
                entity_type="import_run_chunk",
                entity_id=f"{run_id}:{chunk_idx}",
                action="product.import.chunk_completed",
                actor_id=actor.id,
                actor_email=actor.email,
                payload_diff={
                    "chunk_index": chunk_idx,
                    "start_row": start_row,
                    "end_row": end_row,
                    "created": chunk_res.created,
                    "updated": chunk_res.updated,
                    "skipped_locked": chunk_res.skipped_locked,
                    "no_change": chunk_res.no_change,
                    "errors": chunk_res.errors,
                    "failed": chunk_res.failed,
                },
                reason=f"PIM import run {run_id} chunk {chunk_idx} summary",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Importer: failed to audit chunk summary")

        result.chunks.append(chunk_res)

    result.finished_at = datetime.now(tz=timezone.utc)
    return result


# Conveniencia exportada también como `apply_run` para alias semántico.
apply_run = apply_diffs_chunked
