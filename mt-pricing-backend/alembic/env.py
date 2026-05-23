"""Alembic env — sync engine con psycopg + autogenerate desde `app.db.models`.

ADR-049: migration discipline.
- URL viene de `Settings.ALEMBIC_DATABASE_URL` (driver psycopg sync, port 5432
  session pooler de Supabase). Alembic es síncrono por naturaleza; el pooler
  transaction (port 6543) NO soporta prepared statements de asyncpg.
- `compare_type=True` y `compare_server_default=True` para diff fidelity.
- Importamos `app.db.models` para que `Base.metadata` tenga todas las tablas.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# IMPORTANTE: importar Base + todos los modelos para registrar metadata.
from app.core.config import settings
from app.db import models as _models
from app.db.base import Base

config = context.config

# Siempre usar ALEMBIC_DATABASE_URL (psycopg sync, port 5432 session mode).
config.set_main_option("sqlalchemy.url", str(settings.ALEMBIC_DATABASE_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Conecta con sync engine (psycopg) y aplica migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
