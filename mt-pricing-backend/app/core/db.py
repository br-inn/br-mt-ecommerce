"""Backwards-compatible re-export — la implementación real vive en ``app.db``.

Este módulo existió como placeholder en el skeleton original (Agente B).
Agente C montó la implementación canónica en ``app.db`` (engine.py, session.py,
base.py, mixins.py, types.py, enums.py, models/). Aquí mantenemos los nombres
para que cualquier import legacy (`from app.core.db import get_session`) siga
funcionando, pero las nuevas referencias deben usar ``app.db``.
"""

from __future__ import annotations

from app.db import (
    Base,
    dispose_engine,
    get_db_session,
    get_engine,
    get_sessionmaker,
    make_engine,
)

# Alias histórico — `get_session` era el nombre del placeholder original.
get_session = get_db_session

__all__ = [
    "Base",
    "dispose_engine",
    "get_db_session",
    "get_engine",
    "get_session",
    "get_sessionmaker",
    "make_engine",
]


def __getattr__(name: str):  # PEP 562 — lazy compat shim
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_sessionmaker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
