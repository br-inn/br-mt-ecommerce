"""Applier — persiste filas en `material_compatibilities` (US-1A-06-03).

Modos:
- ``replace`` (default): TRUNCATE + INSERT — idempotente, re-cargas válidas.
- ``append``: sólo INSERT — para diffs futuros (no usado en S3).

Acepta un repository inyectable (con un Protocol mínimo) — facilita unit tests
sin DB real. La firma del repo ``replace_all(rows)`` y ``insert_many(rows)`` es
consistente con la convención de otros repos del proyecto.

Schema de fila persistida (matchea el modelo SQLAlchemy):
    {producto_descriptor, temperatura_c, compatibilities (JSONB)}
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from app.services.importer_materials.parser import MaterialRow

logger = logging.getLogger(__name__)


class MaterialCompatibilitiesRepoProtocol(Protocol):
    async def replace_all(self, rows: Sequence[dict[str, Any]]) -> int: ...
    async def insert_many(self, rows: Sequence[dict[str, Any]]) -> int: ...


@dataclass(slots=True)
class ApplyMaterialsResult:
    total_rows: int
    inserted: int = 0
    truncated: bool = False
    errors: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "inserted": self.inserted,
            "truncated": self.truncated,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "failure_details": self.failure_details[:50],
        }


def _row_to_dict(r: MaterialRow) -> dict[str, Any]:
    return {
        "producto_descriptor": r.producto_descriptor,
        "temperatura_c": r.temperatura_c,
        "compatibilities": dict(r.compatibilities),
    }


async def apply_material_rows(
    rows: Sequence[MaterialRow],
    *,
    repo: MaterialCompatibilitiesRepoProtocol,
    mode: str = "replace",
) -> ApplyMaterialsResult:
    """Persiste las filas válidas. Las rows con ``errors`` se ignoran y se
    reportan en ``failure_details``."""
    if mode not in ("replace", "append"):
        raise ValueError(f"mode inválido: {mode!r}")

    valid: list[dict[str, Any]] = []
    failure_details: list[dict[str, Any]] = []
    err_count = 0
    for r in rows:
        if r.errors or not r.ok:
            err_count += 1
            failure_details.append(
                {
                    "row_index": r.row_index,
                    "descriptor": r.producto_descriptor,
                    "reasons": r.errors,
                }
            )
            continue
        valid.append(_row_to_dict(r))

    result = ApplyMaterialsResult(
        total_rows=len(rows),
        errors=err_count,
        failure_details=failure_details,
        started_at=datetime.now(tz=timezone.utc),
    )
    try:
        if mode == "replace":
            inserted = await repo.replace_all(valid)
            result.truncated = True
        else:
            inserted = await repo.insert_many(valid)
        result.inserted = inserted
    finally:
        result.finished_at = datetime.now(tz=timezone.utc)
    return result
