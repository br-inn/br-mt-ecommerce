"""promote_model.py — CLI para promover un modelo embedding candidate → active.

Uso::

    python -m scripts.poc.promote_model --model-id <uuid> --env staging

El script:
1. Conecta a DB via DATABASE_URL.
2. Busca el registro por ``id``, verifica ``status='candidate'``.
3. Si no existe o no es candidate → error con mensaje claro, exit 1.
4. Actualiza ``status='active'`` para el modelo seleccionado.
5. Actualiza ``status='retired'`` para el modelo anteriormente ``active``
   (si existe).
6. Imprime JSON: ``{"promoted": "<uuid>", "retired": "<uuid>|null", "env": "<env>"}``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_database_url() -> str:
    """Lee DATABASE_URL desde el entorno."""
    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        print(
            "ERROR: DATABASE_URL no está definida en el entorno.",
            file=sys.stderr,
        )
        sys.exit(1)
    # asyncpg requiere postgresql+asyncpg:// — convertir si viene como postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _make_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Core promotion logic
# ---------------------------------------------------------------------------


async def _promote(
    model_id: str,
    env: str,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Ejecuta la promoción dentro de una transacción.

    Returns:
        Dict con promoted/retired/env.

    Raises:
        SystemExit: Si el modelo no existe o no es candidate.
    """
    from app.db.models.comparator import ComparatorModelRegistry

    try:
        target_uuid = uuid.UUID(model_id)
    except ValueError:
        print(
            f"ERROR: '{model_id}' no es un UUID válido.",
            file=sys.stderr,
        )
        sys.exit(1)

    async with sessionmaker() as session:
        async with session.begin():
            # 1. Buscar el modelo objetivo
            stmt = select(ComparatorModelRegistry).where(ComparatorModelRegistry.id == target_uuid)
            target = (await session.execute(stmt)).scalar_one_or_none()

            if target is None:
                print(
                    f"ERROR: No existe ningún modelo con id='{model_id}'.",
                    file=sys.stderr,
                )
                sys.exit(1)

            if target.status != "candidate":
                print(
                    f"ERROR: El modelo '{model_id}' tiene status='{target.status}', "
                    "se esperaba 'candidate'.",
                    file=sys.stderr,
                )
                sys.exit(1)

            # 2. Buscar el modelo actualmente active (si existe)
            stmt_active = select(ComparatorModelRegistry).where(
                ComparatorModelRegistry.status == "active"
            )
            current_active = (await session.execute(stmt_active)).scalar_one_or_none()
            retired_id: str | None = None

            if current_active is not None and current_active.id != target_uuid:
                current_active.status = "retired"
                retired_id = str(current_active.id)

            # 3. Promover el modelo objetivo
            target.status = "active"

    return {
        "promoted": str(target_uuid),
        "retired": retired_id,
        "env": env,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promueve un modelo embedding candidate → active.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model-id",
        required=True,
        metavar="UUID",
        help="UUID del modelo a promover (status debe ser 'candidate').",
    )
    parser.add_argument(
        "--env",
        default="staging",
        choices=["staging", "production"],
        help="Entorno destino (informativo — se incluye en el output JSON).",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    database_url = _get_database_url()
    sessionmaker = _make_sessionmaker(database_url)
    result = await _promote(
        model_id=args.model_id,
        env=args.env,
        sessionmaker=sessionmaker,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(_main())
