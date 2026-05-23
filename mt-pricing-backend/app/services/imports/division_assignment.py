"""Division assignment helper para importers PIM (Stage 3 Wave 11).

Resuelve `division_codes` (lista de strings, e.g. `["hidrosanitario"]`) →
``division_id`` UUID via :class:`DivisionRepo` y crea links idempotentes en
``product_divisions`` usando :class:`ProductDivisionRepo`.

Diseño:
- **Idempotente**: re-llamar con los mismos códigos no duplica filas (el repo
  ya hace ``get_link`` antes de insertar).
- **No-op si vacío**: si ``division_codes`` está vacío o None, no toca BD.
- **Cache por llamada**: resolvemos cada code → id una sola vez por invocación
  (importers procesan miles de filas — evita N queries inútiles al vocab).
- **Códigos desconocidos**: skip + warning. La razón: en bulk import un código
  mal escrito en ``settings.PIM_DEFAULT_DIVISIONS`` o en el run summary no debe
  abortar miles de upserts. El warning queda en logs para que TI lo corrija
  fuera de banda.

Comentarios en español; nombres en inglés.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.vocabularies import DivisionRepo, ProductDivisionRepo

logger = logging.getLogger(__name__)


async def assign_divisions(
    session: AsyncSession,
    product_sku: str,
    division_codes: list[str] | None,
    *,
    code_id_cache: dict[str, UUID | None] | None = None,
) -> int:
    """Asigna divisiones a un producto por code → idempotente.

    Args:
        session: ``AsyncSession`` con transacción activa (el caller controla
            commit). Toda escritura va vía repo + ``flush()``.
        product_sku: SKU del producto destino. Se asume que ya existe (FK
            CASCADE protege contra orfandad).
        division_codes: lista de codes (e.g. ``["hidrosanitario","industrial"]``)
            a asignar. ``None`` o ``[]`` → no-op.
        code_id_cache: cache opcional ``code → division_id`` compartido entre
            llamadas dentro del mismo import run. Si se provee, lo poblamos.

    Returns:
        ``int`` — número de links efectivamente creados (0 si todos ya existían
        o lista vacía).

    Notes:
        - Códigos desconocidos producen warning + skip (NO abortan).
        - Re-llamar con los mismos códigos devuelve 0 (idempotencia confirmada).
    """
    if not division_codes:
        return 0

    div_repo = DivisionRepo(session)
    pd_repo = ProductDivisionRepo(session)

    cache: dict[str, UUID | None] = code_id_cache if code_id_cache is not None else {}

    created = 0
    for code in division_codes:
        if not code or not str(code).strip():
            continue
        code_norm = str(code).strip()

        # Resolve code → division_id (cache-first).
        if code_norm not in cache:
            div = await div_repo.get_by_code(code_norm)
            cache[code_norm] = div.id if div else None

        div_id = cache[code_norm]
        if div_id is None:
            logger.warning(
                "assign_divisions: código %r desconocido, skip (sku=%s).",
                code_norm,
                product_sku,
            )
            continue

        # Idempotent link — el repo hace get_link → upsert.
        existing = await pd_repo.get_link(product_sku, div_id)
        if existing is None:
            await pd_repo.link(product_sku, div_id)
            created += 1

    return created


__all__ = ["assign_divisions"]
