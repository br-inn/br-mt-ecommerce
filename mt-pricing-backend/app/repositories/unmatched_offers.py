"""UnmatchedOfferRepository — CRUD + matching lifecycle para `unmatched_offers`.

Cumple el contrato de :class:`BaseRepository` (PK UUID `id`). Metodos de
negocio:
- ``upsert_from_raw``  — INSERT-or-touch por fingerprint SHA-256.
- ``get_pending_batch`` — lote de ofertas sin match para el pipeline.
- ``mark_matched``      — registra timestamp de match exitoso.
- ``increment_attempts`` — conteo de intentos via SQL UPDATE.

No commitea — el caller es responsable de la transaccion.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update

from app.db.models.unmatched_offer import UnmatchedOffer
from app.repositories.base import BaseRepository
from app.services.matching.ports import CandidateRaw

logger = logging.getLogger(__name__)


class UnmatchedOfferRepository(BaseRepository[UnmatchedOffer]):
    model = UnmatchedOffer
    pk_field = "id"
    soft_delete_field = None

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def upsert_from_raw(self, raw: CandidateRaw, *, source_sku: str | None = None) -> UnmatchedOffer:
        """Inserta o toca la fila correspondiente a `raw`.

        El fingerprint se calcula como SHA-256 de ``"<source>|<external_id>"``.
        Si ya existe una fila con ese fingerprint solo actualiza `updated_at`
        via flush (el contenido no cambia — es la misma oferta).
        Si no existe, crea una fila nueva con `source_sku` si se provee.
        """
        fingerprint = hashlib.sha256(
            f"{raw.source}|{raw.external_id}".encode()
        ).hexdigest()

        stmt = select(UnmatchedOffer).where(UnmatchedOffer.fingerprint == fingerprint)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Misma oferta — solo forzar updated_at via flush. No actualizar source_sku (append-only).
            await self.session.flush()
            return existing

        embedding = _generate_embedding(raw.title, raw.brand, raw.specs or {})

        return await self.create(
            marketplace=raw.source,
            external_id=raw.external_id,
            title=raw.title,
            brand=raw.brand,
            price_aed=raw.price_aed,
            delivery_text=raw.delivery_text,
            specs_jsonb=raw.specs,
            fingerprint=fingerprint,
            embedding=embedding,
            source_sku=source_sku,
        )

    # ------------------------------------------------------------------
    # Batch retrieval
    # ------------------------------------------------------------------

    async def get_pending_batch(self, limit: int = 100) -> list[UnmatchedOffer]:
        """Devuelve hasta `limit` ofertas sin match con menos de 3 intentos.

        Ordenadas por `scraped_at DESC` (las mas recientes primero).
        """
        stmt = (
            select(UnmatchedOffer)
            .where(
                UnmatchedOffer.matched_at.is_(None),
                UnmatchedOffer.match_attempts < 3,
            )
            .order_by(UnmatchedOffer.scraped_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_for_sku(self, source_sku: str, limit: int = 50) -> list[UnmatchedOffer]:
        """Devuelve ofertas del pool que fueron scrapeadas para un SKU específico.

        Filtra por source_sku, sin match, con menos de 3 intentos.
        """
        stmt = (
            select(UnmatchedOffer)
            .where(
                UnmatchedOffer.source_sku == source_sku,
                UnmatchedOffer.matched_at.is_(None),
                UnmatchedOffer.match_attempts < 3,
            )
            .order_by(UnmatchedOffer.scraped_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def mark_matched(self, offer_id: UUID) -> None:
        """Registra `matched_at = now(UTC)` en la oferta indicada."""
        obj = await self.get(offer_id)
        if obj is None:
            return
        obj.matched_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def increment_attempts(self, offer_id: UUID) -> None:
        """Incrementa `match_attempts` en 1 via SQL UPDATE (sin fetch ORM)."""
        stmt = (
            update(UnmatchedOffer)
            .where(UnmatchedOffer.id == offer_id)
            .values(match_attempts=UnmatchedOffer.match_attempts + 1)
        )
        await self.session.execute(stmt)

    # ------------------------------------------------------------------
    # Filtered list (API)
    # ------------------------------------------------------------------

    async def list_with_filters(
        self,
        *,
        marketplace: str | None = None,
        status: str | None = None,
        source_sku: str | None = None,
        q: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[UnmatchedOffer], UUID | None]:
        """Cursor-paginated list. Returns (items, next_cursor).

        ORDER BY scraped_at DESC, id DESC.
        Cursor encodes the id of the last returned row; keyset pagination is
        implemented as id < cursor with that row's scraped_at tiebreak.
        """
        conditions = []

        if marketplace is not None:
            conditions.append(UnmatchedOffer.marketplace == marketplace)

        if status == "pending":
            conditions.append(UnmatchedOffer.matched_at.is_(None))
            conditions.append(UnmatchedOffer.match_attempts < 3)
        elif status == "matched":
            conditions.append(UnmatchedOffer.matched_at.isnot(None))
        elif status == "exhausted":
            conditions.append(UnmatchedOffer.matched_at.is_(None))
            conditions.append(UnmatchedOffer.match_attempts >= 3)

        if source_sku is not None:
            conditions.append(UnmatchedOffer.source_sku == source_sku)

        if q is not None:
            conditions.append(UnmatchedOffer.title.ilike(f"%{q}%"))

        # Cursor: keyset on (scraped_at DESC, id DESC).
        # Fetch the cursor row first to get its scraped_at for the compound predicate.
        if cursor is not None:
            cursor_row_stmt = select(UnmatchedOffer).where(UnmatchedOffer.id == cursor)
            cursor_result = await self.session.execute(cursor_row_stmt)
            cursor_row = cursor_result.scalar_one_or_none()
            if cursor_row is not None:
                # (scraped_at, id) < (cursor_scraped_at, cursor_id) in DESC order means
                # scraped_at < cursor_scraped_at OR (scraped_at == cursor_scraped_at AND id < cursor_id)
                from sqlalchemy import and_, or_  # noqa: PLC0415
                conditions.append(
                    or_(
                        UnmatchedOffer.scraped_at < cursor_row.scraped_at,
                        and_(
                            UnmatchedOffer.scraped_at == cursor_row.scraped_at,
                            UnmatchedOffer.id < cursor,
                        ),
                    )
                )

        stmt = (
            select(UnmatchedOffer)
            .where(*conditions)
            .order_by(UnmatchedOffer.scraped_at.desc(), UnmatchedOffer.id.desc())
            .limit(limit + 1)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: UUID | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = rows[-1].id

        return rows, next_cursor

    async def get_stats(self) -> dict[str, int]:
        """Returns counts for the /stats endpoint."""
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        total_pending_stmt = select(func.count()).where(
            UnmatchedOffer.matched_at.is_(None),
            UnmatchedOffer.match_attempts < 3,
        )
        total_matched_stmt = select(func.count()).where(
            UnmatchedOffer.matched_at.isnot(None),
        )
        total_exhausted_stmt = select(func.count()).where(
            UnmatchedOffer.matched_at.is_(None),
            UnmatchedOffer.match_attempts >= 3,
        )
        matched_24h_stmt = select(func.count()).where(
            UnmatchedOffer.matched_at.isnot(None),
            UnmatchedOffer.matched_at >= last_24h,
        )
        scraped_7d_stmt = select(func.count()).where(
            UnmatchedOffer.scraped_at >= last_7d,
        )

        results = await self.session.execute(total_pending_stmt)
        total_pending = results.scalar_one()
        results = await self.session.execute(total_matched_stmt)
        total_matched = results.scalar_one()
        results = await self.session.execute(total_exhausted_stmt)
        total_exhausted = results.scalar_one()
        results = await self.session.execute(matched_24h_stmt)
        matched_last_24h = results.scalar_one()
        results = await self.session.execute(scraped_7d_stmt)
        scraped_last_7d = results.scalar_one()

        return {
            "total_pending": total_pending,
            "total_matched": total_matched,
            "total_exhausted": total_exhausted,
            "matched_last_24h": matched_last_24h,
            "scraped_last_7d": scraped_last_7d,
        }

    # ------------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------------

    async def find_similar(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        max_age_days: int = 7,
        min_similarity: float = 0.75,
    ) -> list[tuple[UnmatchedOffer, float]]:
        """Busca ofertas semanticamente similares usando pgvector cosine distance.

        Retorna lista de (oferta, similarity_score) ordenada por similitud DESC.
        Solo considera ofertas sin match, con embedding generado, dentro del TTL.
        `min_similarity` filtra resultados por debajo del umbral (0-1).
        """
        stmt = (
            select(
                UnmatchedOffer,
                (1 - UnmatchedOffer.embedding.cosine_distance(embedding)).label("similarity"),
            )
            .where(
                UnmatchedOffer.matched_at.is_(None),
                UnmatchedOffer.embedding.isnot(None),
                text(f"scraped_at > NOW() - INTERVAL '{max_age_days} days'"),
            )
            .order_by(UnmatchedOffer.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            (row.UnmatchedOffer, float(row.similarity))
            for row in rows
            if float(row.similarity) >= min_similarity
        ]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _generate_embedding(
    title: str, brand: str | None, specs: dict[str, Any]
) -> list[float] | None:
    """Genera embedding local con sentence-transformers. Falla silenciosamente."""
    try:
        from app.services.matching.embeddings import embed_offer  # lazy — no en startup

        return embed_offer(title, brand, specs)
    except Exception:
        logger.warning("unmatched_offer.embedding_failed", extra={"title": title[:80]}, exc_info=True)
        return None
