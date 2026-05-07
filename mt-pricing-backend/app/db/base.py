"""Declarative Base — SQLAlchemy 2.0 con AsyncAttrs.

Decisión (ver `mt-sqlalchemy-models.md` §1):
- NO se usa `MappedAsDataclass`: muchos modelos (audit, jobs, kb) tienen
  `__table_args__` con tuplas + dict que conviven mejor con la sintaxis ORM
  tradicional, y los defaults `None` en campos opcionales no se beneficiarían
  de `kw_only=True` aquí.
- Sí se usa `AsyncAttrs` para habilitar `await obj.awaitable_attrs.foo` sin
  forzar eager loading desde el modelo.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base compartida por todos los modelos del proyecto.

    Todas las tablas deben declarar `__tablename__` explícito y FK con
    `ondelete=` explícito (CASCADE | SET NULL | RESTRICT).
    """
