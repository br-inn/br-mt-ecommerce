"""Tipos auxiliares y helpers DDL.

- `UUID_PK`: server_default `gen_random_uuid()` (TODO migrar a `uuid_generate_v7()`
  cuando `pg_uuidv7` esté en el plan Pro de Supabase — ADR-031).
- `JSONB_DICT` / `JSONB_LIST`: alias tipados para columnas JSONB con valores por
  defecto `'{}'::jsonb` / `'[]'::jsonb` ya cableados.
- `Vector1024`: alias condicional para `pgvector.sqlalchemy.Vector(1024)` si la
  librería está instalada; si no, `ARRAY(Float)` como fallback (Sprint 1 no usa
  embeddings — ver TODO al final del fichero).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.types import TypeDecorator, TypeEngine

# ---------------------------------------------------------------------------
# UUID v7 — server side
# ---------------------------------------------------------------------------
# Postgres `pg_uuidv7` aún no GA en plan Free de Supabase; usamos
# `gen_random_uuid()` (pgcrypto) y dejamos el switch como ALTER posterior.
UUID_DEFAULT_SQL = text("gen_random_uuid()")

# Convenience alias — no es un tipo `Mapped`, sólo el TypeEngine concreto.
UUID_PG: TypeEngine[Any] = PgUUID(as_uuid=True)


# ---------------------------------------------------------------------------
# JSONB defaults
# ---------------------------------------------------------------------------
JSONB_OBJECT_DEFAULT = text("'{}'::jsonb")
JSONB_ARRAY_DEFAULT = text("'[]'::jsonb")


# ---------------------------------------------------------------------------
# pgvector — opcional Sprint 1 (los modelos lo declaran nullable)
# ---------------------------------------------------------------------------
try:  # pragma: no cover — depende de que `pgvector` esté instalada
    from pgvector.sqlalchemy import Vector  # type: ignore[import-not-found]

    Vector1024: type[TypeEngine[Any]] = Vector(1024)  # type: ignore[assignment, misc]
    HAS_PGVECTOR = True
except ImportError:  # pragma: no cover
    # Fallback: ARRAY(Float) — funcionalmente equivalente para CRUD pero sin
    # operadores de similaridad ANN. Sprint 1 no consume embeddings.
    Vector1024 = ARRAY(Float)  # type: ignore[assignment]
    HAS_PGVECTOR = False


class JSONBValidatedDict(TypeDecorator[dict[str, Any]]):
    """JSONB que fuerza dict en Python — evita guardar None accidentales como JSONB null."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:  # noqa: ANN401
        if value is None:
            return {}
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ANN401
        return value if value is not None else {}


# TODO(Sprint 2):
# - Migrar `UUID_DEFAULT_SQL` → `uuid_generate_v7()` cuando pg_uuidv7 esté
#   habilitado en Supabase Pro.
# - Sustituir `Vector1024` placeholder por la implementación real cuando se
#   active el módulo de embeddings (ADR-011).
