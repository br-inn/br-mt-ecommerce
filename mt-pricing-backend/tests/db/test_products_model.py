"""US-1A-02-01-S1 — DoD: modelo `Product` SQLAlchemy + constraints.

CRUD básico contra Postgres efímero. Los tests RLS van por separado en
`test_supabase_rls.py` (S2 — requiere supabase real).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Aplica `alembic upgrade head` antes de los tests."""
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_create_product_minimal_roundtrip(db_session: AsyncSession) -> None:
    """Crear con campos mínimos (sku, family) y leerlo back."""
    from app.db.models import Product

    p = Product(sku="MT-V-038", family="gate_valve")
    db_session.add(p)
    await db_session.flush()

    # Server defaults
    assert p.lifecycle_status == "active"
    assert p.data_quality == "partial"
    assert p.specs == {}

    # Read
    stmt = select(Product).where(Product.sku == "MT-V-038")
    fetched = (await db_session.execute(stmt)).scalar_one()
    assert fetched.family == "gate_valve"
    assert fetched.internal_id is not None  # gen_random_uuid()
    assert fetched.created_at is not None  # now()


async def test_product_specs_jsonb_persistence(db_session: AsyncSession) -> None:
    """JSONB roundtrip: el dict Python sobrevive el viaje a Postgres."""
    from app.db.models import Product

    specs = {"pressure": "PN16", "temperature_max": 200, "tags": ["api", "iso"]}
    p = Product(
        sku="MT-V-100",
        family="ball_valve",
        specs=specs,
        dimensions={"length_mm": 220, "weight_kg": 4.5},
    )
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)

    assert p.specs == specs
    assert p.dimensions["length_mm"] == 220


async def test_product_data_quality_check_constraint(db_session: AsyncSession) -> None:
    """CHECK ck_products_data_quality: rechaza valores fuera del enum."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO products (sku, family, data_quality) "
                "VALUES ('MT-V-BAD', 'ball_valve', 'INVALID_VALUE');"
            )
        )
        await db_session.flush()


async def test_product_translation_cascade_on_delete(db_session: AsyncSession) -> None:
    """ProductTranslation se borra al borrar el Product (FK ondelete=CASCADE)."""
    from app.db.models import Product, ProductTranslation

    p = Product(sku="MT-V-CAS", family="gate_valve")
    db_session.add(p)
    await db_session.flush()

    t = ProductTranslation(sku="MT-V-CAS", lang="es", name="Válvula de prueba")
    db_session.add(t)
    await db_session.flush()

    # Delete parent → child desaparece
    await db_session.execute(text("DELETE FROM products WHERE sku = 'MT-V-CAS';"))
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT count(*) FROM product_translations WHERE sku = 'MT-V-CAS';")
    )
    assert result.scalar_one() == 0


async def test_seed_roles_present(db_session: AsyncSession) -> None:
    """Los 4 roles canónicos quedan seedados por la migración 001."""
    result = await db_session.execute(text("SELECT code FROM roles ORDER BY code;"))
    codes = {r[0] for r in result.all()}
    assert codes >= {"admin", "comercial", "gerente_comercial", "ti_integracion"}
