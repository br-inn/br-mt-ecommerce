"""Database layer (SQLAlchemy 2.0 async).

Public surface:
- ``Base`` — DeclarativeBase compartido (importable como ``from app.db import Base``).
- ``engine`` — singleton AsyncEngine (asyncpg).
- ``AsyncSessionLocal`` — async_sessionmaker.
- ``get_db_session`` — FastAPI dependency.

Los modelos concretos viven en ``app.db.models`` y se importan ahí para
que Alembic los descubra via ``Base.metadata``.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.engine import (
    dispose_engine,
    get_engine,
    get_sessionmaker,
    make_engine,
)
from app.db.session import get_db_session

__all__ = [
    "Base",
    "dispose_engine",
    "get_db_session",
    "get_engine",
    "get_sessionmaker",
    "make_engine",
]


def __getattr__(name: str):  # PEP 562 — exporta `engine` / `AsyncSessionLocal` lazy.
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
