"""Repositories layer — pure data access sobre SQLAlchemy 2.0 async (ADR-045).

Convenciones:
- Un repository por agregado de dominio (Product, User, ...).
- Repos NUNCA hacen `.commit()` — eso lo hace el dependency `get_db_session`
  (commit-on-success / rollback-on-error).
- Repos reciben `AsyncSession` por inyección, nunca la crean.
- Sin lógica de negocio aquí — vive en `app/services/<dominio>/`.
"""

from __future__ import annotations

from app.repositories.audit import AuditRepository
from app.repositories.base import BaseRepository
from app.repositories.job import JobDefinitionRepository, JobRunRepository
from app.repositories.product import (
    ProductImageRepository,
    ProductRepository,
    ProductTranslationRepository,
)
from app.repositories.user import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)

__all__ = [
    "AuditRepository",
    "BaseRepository",
    "JobDefinitionRepository",
    "JobRunRepository",
    "PermissionRepository",
    "ProductImageRepository",
    "ProductRepository",
    "ProductTranslationRepository",
    "RoleRepository",
    "UserRepository",
]
