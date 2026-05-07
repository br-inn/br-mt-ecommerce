"""US-1A-01-08-S1 — DoD: import smoke.

Garantiza que `app.db.models.__init__` registra TODOS los modelos en
`Base.metadata`, condición necesaria para que Alembic autogenerate los
detecte. Si alguien añade un modelo nuevo y olvida re-exportarlo, este test
falla.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_all_models_importable_and_registered() -> None:
    """Importar `app.db.models` debe poblar Base.metadata.tables con todas las tablas Sprint 1."""
    from app.db import Base
    from app.db import models as _  # noqa: F401 — side-effect: registra mappers

    expected_tables = {
        # Users / RBAC
        "users",
        "roles",
        "permissions",
        "role_permissions",
        # Products
        "products",
        "product_translations",
        "product_images",
        # Audit
        "audit_events",
        # Jobs / scheduler
        "job_definitions",
        "job_runs",
    }

    registered = set(Base.metadata.tables.keys())
    missing = expected_tables - registered
    assert not missing, f"Modelos no registrados en Base.metadata: {missing}"


def test_models_public_api_exports() -> None:
    """`app.db.models` re-exporta los nombres canónicos."""
    from app.db import models

    expected = {
        "User",
        "Role",
        "Permission",
        "RolePermission",
        "Product",
        "ProductTranslation",
        "ProductImage",
        "AuditEvent",
        "JobDefinition",
        "JobRun",
    }
    actual = set(models.__all__)
    missing = expected - actual
    assert not missing, f"Faltan en `app.db.models.__all__`: {missing}"


def test_db_layer_public_surface() -> None:
    """`from app.db import Base, get_db_session, make_engine` resuelve."""
    from app.db import Base, dispose_engine, get_db_session, get_engine, get_sessionmaker, make_engine

    assert callable(make_engine)
    assert callable(get_engine)
    assert callable(get_sessionmaker)
    assert callable(get_db_session)
    assert callable(dispose_engine)
    assert Base is not None
    # Sanity — `Base.metadata` accesible.
    assert hasattr(Base, "metadata")


def test_products_table_has_required_columns() -> None:
    """US-1A-02-01-S1 — schema de `products` tiene los campos del PRD §4."""
    from app.db import Base
    from app.db import models as _  # noqa: F401

    products = Base.metadata.tables["products"]
    cols = set(products.columns.keys())

    required = {
        "sku",
        "internal_id",
        "name_en",
        "family",
        "brand",
        "dn",
        "pn",
        "material",
        "specs",
        "active",
        "data_quality",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "deleted_at",
    }
    missing = required - cols
    assert not missing, f"products faltan columnas PRD §4: {missing}"

    # PK = sku (TEXT) — architecture §8.4.
    pk_cols = {c.name for c in products.primary_key.columns}
    assert pk_cols == {"sku"}, f"PK de products debe ser {{'sku'}}, encontrado {pk_cols}"


def test_audit_events_table_has_required_columns() -> None:
    """US-1A-07-01-S1 — schema de `audit_events` cumple architecture §8.10."""
    from app.db import Base
    from app.db import models as _  # noqa: F401

    audit = Base.metadata.tables["audit_events"]
    cols = set(audit.columns.keys())

    required = {
        "id",
        "event_at",
        "actor_id",
        "actor_email",
        "actor_role",
        "entity_type",
        "entity_id",
        "action",
        "before",
        "after",
        "payload_diff",
        "reason",
        "prev_hash",
        "current_hash",
        "request_id",
        "ip_address",
        "user_agent",
    }
    missing = required - cols
    assert not missing, f"audit_events faltan columnas: {missing}"

    # PK compuesta (id, event_at) requerida por PARTITION BY RANGE event_at.
    pk = {c.name for c in audit.primary_key.columns}
    assert pk == {"id", "event_at"}, f"PK debe ser (id, event_at): {pk}"


def test_alembic_revision_chain_resolves() -> None:
    """Alembic puede resolver el árbol de migraciones sin ambigüedad (single head)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected single head, got {heads}"
    # First migration es 20260506_001 (initial_schema).
    base = script.get_base()
    assert base == "20260506_001"
