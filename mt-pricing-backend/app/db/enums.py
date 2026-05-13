"""Python enums alineados 1:1 con valores almacenados en BD.

Estrategia DDL (ver `mt-sqlalchemy-models.md` §13):
- Las columnas se declaran como `String(N) + CHECK constraint`, NO como
  `Enum(create_type=True)`. Razones:
    1. Alembic autogenerate no detecta cambios de valores de enum
       (requiere `op.execute("ALTER TYPE ... ADD VALUE")` manual).
    2. Importar el mismo enum desde dos modelos puede duplicar el
       `CREATE TYPE` y romper la migración.
    3. `String + CHECK` permite ALTERs lineales y diff-friendly.
- Los enums Python siguen siendo la única fuente de verdad de los valores
  posibles — usados por Pydantic para validar, y por el repositorio para
  filtrar.
"""

from __future__ import annotations

from enum import StrEnum


class PriceState(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    # Legacy — mantenidos por backward-compat con datos históricos
    REVISED = "revised"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"
    MIGRATED = "migrated"


# Alias semántico usado en US-1B-02 (workflow aprobación)
PriceStatus = PriceState


class ChannelState(StrEnum):
    INACTIVE = "inactive"
    PRE_LAUNCH = "pre_launch"
    PILOT = "pilot"
    LIVE = "live"
    PAUSED = "paused"
    DEPRECATED = "deprecated"


class Scheme(StrEnum):
    FBA = "FBA"
    FBM = "FBM"
    DIRECT_B2C = "DIRECT_B2C"
    DIRECT_B2B = "DIRECT_B2B"
    MARKETPLACE = "MARKETPLACE"


class TranslationStatus(StrEnum):
    PENDING = "pending"
    DRAFT = "draft"
    APPROVED = "approved"


class DataQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    MIGRATED_DEMO = "migrated_demo"


class ImportStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    VALIDATING = "validating"
    PREVIEW_READY = "preview_ready"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class JobOwner(StrEnum):
    INFRA = "infra"
    BUSINESS = "business"


class ScheduleType(StrEnum):
    CRON = "cron"
    INTERVAL = "interval"


class MatchStatus(StrEnum):
    UNMATCHED = "unmatched"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ImageStatus(StrEnum):
    """Estado del pipeline de mirror de una imagen externa.

    Usado por el worker `app.workers.probe_mirror.probe_and_mirror_image` para
    señalizar el ciclo de vida de la copia de una URL externa al bucket
    `product-images`. Distinto de `ProductImage.status` (active/archived/broken)
    que es semántico-de-negocio.
    """

    PENDING = "pending"
    MIRRORING = "mirroring"
    MIRRORED = "mirrored"
    FAILED = "failed"


class POStatus(StrEnum):
    """Estado de ciclo de vida de un Purchase Order (EP-INV-01)."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class GRStatus(StrEnum):
    """Estado de procesamiento de un Goods Receipt (EP-INV-01)."""

    PENDING = "pending"
    PROCESSED = "processed"
    ERROR = "error"


class LifecycleStatus(StrEnum):
    """Ciclo de vida de un producto (M1-05).

    Transiciones válidas: draft → in_review → active → discontinued.
    deprecated/replaced conservados por compat con datos históricos.
    """

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REPLACED = "replaced"
    DISCONTINUED = "discontinued"


class ReleaseStatus(StrEnum):
    """Estado del lanzamiento de un producto a un mercado (M1-01)."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISCONTINUED = "discontinued"


# Helpers para CHECK constraints en migraciones —
# evita repetir las listas de valores en SQL crudo.
def values_csv(enum_cls: type[StrEnum]) -> str:
    """Renderiza ('a','b','c') para usar en CHECK constraints."""
    return "(" + ",".join(f"'{m.value}'" for m in enum_cls) + ")"
