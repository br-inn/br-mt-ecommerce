"""Integration tests for the XML branch of PimImporter (Task 7).

Verifica que PimImporter.run() ingiera correctamente una fuente .xml:
- Producto creado con campo escalar (family).
- ProductRelease creado (rich block _releases).
- status=completed | completed_with_errors.
- inserted_rows == 1.
"""

from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.import_run import ImportRun
from app.db.models.product import Product, ProductRelease
from app.services.imports.pim_importer import PimImporter

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config  # noqa: I001
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def _cleanup(db_session: AsyncSession):
    await db_session.execute(text("TRUNCATE TABLE products CASCADE;"))
    await db_session.execute(text("DELETE FROM import_runs;"))
    await db_session.commit()
    yield


_NS = "https://mtme-api/schemas/articulos/v1"
_XML = (
    f'<catalog xmlns="{_NS}"><article><sku>MT-ASYNC-1</sku>'
    f"<name_en>Async Valve</name_en><family>ball_valve</family><dn>25</dn>"
    f"<releases><release market_code=\"UAE\"><local_name>AV</local_name>"
    f"<list_price>50.00</list_price><price_currency>AED</price_currency>"
    f"</release></releases></article></catalog>"
)


async def test_pim_importer_xml_source(db_session: AsyncSession) -> None:
    run = ImportRun(
        import_type="pim",
        source_filename="articulos.xml",
        source_storage_path="x",
        status="queued",
    )
    db_session.add(run)
    await db_session.commit()

    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    Path(path).write_bytes(_XML.encode("utf-8"))
    try:
        importer = PimImporter(
            session=db_session,
            source_path=path,
            run_id=run.id,
            actor_id=None,
        )
        result = await importer.run()
    finally:
        os.unlink(path)

    assert result.status in ("completed", "completed_with_errors"), result.errors
    assert result.inserted_rows == 1
    prod = (
        await db_session.execute(select(Product).where(Product.sku == "MT-ASYNC-1"))
    ).scalar_one()
    assert prod.family == "ball_valve"
    rel = (
        await db_session.execute(
            select(ProductRelease).where(ProductRelease.product_sku == "MT-ASYNC-1")
        )
    ).scalars().all()
    assert len(rel) == 1
    assert rel[0].market_code == "UAE"
