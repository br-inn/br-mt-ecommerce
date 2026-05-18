"""search_query_cache.py — Caché de queries LLM por (SKU, canal).

Evita llamar al LLM en cada refresh. La query se regenera solo cuando:
  1. No existe en la tabla.
  2. El hash del producto cambió (alguien editó el producto).
  3. El usuario marcó `manual_override=True` y pidió regenerar.

Uso:
    query_text = await get_or_generate_query(session, product_data, "amazon_uae")
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.search_query import ProductSearchQuery
from app.services.matching.llm_query_generator import generate_amazon_query

logger = logging.getLogger(__name__)

_MODEL_USED = "claude-haiku-4-5"

# Campos que determinan si el producto cambió lo suficiente para regenerar la query.
_HASH_FIELDS = ("erp_name", "product_type", "material", "dn", "pn", "connection", "alloy")


def _compute_product_hash(product_data: dict[str, Any]) -> str:
    """SHA-256 de los campos clave del producto que afectan la query de búsqueda."""
    payload = {k: str(product_data.get(k) or "") for k in _HASH_FIELDS}
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_or_generate_query(
    session: AsyncSession,
    product_data: dict[str, Any],
    channel: str = "amazon_uae",
    *,
    force_regenerate: bool = False,
) -> str | None:
    """Devuelve la query de búsqueda para (SKU, canal), generándola si es necesario.

    Args:
        session: Sesión async de SQLAlchemy (read + write).
        product_data: Dict del producto (salida de MatchService._product_to_dict()).
        channel: Canal de búsqueda (amazon_uae / noon_uae).
        force_regenerate: Ignorar caché y llamar al LLM incluso si existe.

    Returns:
        Query de búsqueda en inglés, o None si el LLM no está disponible.
    """
    sku = str(product_data.get("sku") or "")
    if not sku:
        return None

    current_hash = _compute_product_hash(product_data)

    # Buscar en caché
    stmt = select(ProductSearchQuery).where(
        ProductSearchQuery.sku == sku,
        ProductSearchQuery.channel == channel,
    )
    row: ProductSearchQuery | None = (await session.execute(stmt)).scalar_one_or_none()

    # Decidir si reutilizar o regenerar
    if not force_regenerate and row is not None:
        if row.manual_override or row.product_hash == current_hash:
            # Hit de caché — actualizar last_used_at sin flush caro
            await session.execute(
                text(
                    "UPDATE product_search_queries SET last_used_at = now() "
                    "WHERE id = :id"
                ),
                {"id": row.id},
            )
            logger.debug(
                "search_query_cache: cache HIT sku=%s channel=%s query=%r",
                sku,
                channel,
                row.query_text,
            )
            return row.query_text
        logger.info(
            "search_query_cache: hash changed sku=%s — regenerating query", sku
        )

    # Cache miss o producto cambió → llamar al LLM
    query_text = await generate_amazon_query(product_data)
    if not query_text:
        # LLM no disponible — retornar query anterior si existe
        if row is not None:
            return row.query_text
        return None

    now = datetime.now(tz=timezone.utc)

    if row is None:
        row = ProductSearchQuery(
            sku=sku,
            channel=channel,
            query_text=query_text,
            product_hash=current_hash,
            model_used=_MODEL_USED,
            manual_override=False,
            generated_at=now,
            last_used_at=now,
        )
        session.add(row)
    else:
        row.query_text = query_text
        row.product_hash = current_hash
        row.model_used = _MODEL_USED
        row.manual_override = False
        row.generated_at = now
        row.last_used_at = now

    await session.flush()

    logger.info(
        "search_query_cache: generated query sku=%s channel=%s query=%r",
        sku,
        channel,
        query_text,
    )
    return query_text


async def set_manual_query(
    session: AsyncSession,
    sku: str,
    channel: str,
    query_text: str,
    product_data: dict[str, Any],
) -> ProductSearchQuery:
    """Permite a un operador sobreescribir la query manualmente.

    Marca `manual_override=True` para que no se regenere automáticamente.
    """
    stmt = select(ProductSearchQuery).where(
        ProductSearchQuery.sku == sku,
        ProductSearchQuery.channel == channel,
    )
    row: ProductSearchQuery | None = (await session.execute(stmt)).scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)
    current_hash = _compute_product_hash(product_data)

    if row is None:
        row = ProductSearchQuery(
            sku=sku,
            channel=channel,
            query_text=query_text,
            product_hash=current_hash,
            model_used="manual",
            manual_override=True,
            generated_at=now,
            last_used_at=now,
        )
        session.add(row)
    else:
        row.query_text = query_text
        row.product_hash = current_hash
        row.model_used = "manual"
        row.manual_override = True
        row.generated_at = now
        row.last_used_at = now

    await session.flush()
    return row


__all__ = ["get_or_generate_query", "set_manual_query"]
