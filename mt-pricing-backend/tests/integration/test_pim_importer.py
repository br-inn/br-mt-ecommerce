"""Integration tests para `app.services.imports.pim_importer.PimImporter`.

Cobertura:
1. Total rows reflejados correctamente en ImportRun.
2. INSERT crea N productos con campos canónicos.
3. SKU duplicado en re-run → updated, no insert.
4. Fila vacia → skipped (no error_row).
5. Numéricos como strings se castean OK.
6. Header mismatch → status='failed' sin tocar productos.

Usa testcontainer Postgres (`db_session` fixture vive en conftest del test
suite) y un xlsx sintético generado en runtime con openpyxl.
"""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Force test env vars BEFORE importing app modules (mirror test_products pattern).
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

from app.db.models.import_run import ImportRun
from app.db.models.product import Product
from app.services.importer.column_mapper import EXPECTED_HEADERS
from app.services.imports.pim_importer import PimImporter

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Aplica `alembic upgrade head` antes de cualquier test del modulo."""
    from alembic.config import Config
    from alembic import command  # noqa: I001

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_products_and_runs(db_session: AsyncSession):
    """PimImporter hace commits explicitos — no podemos confiar en el rollback
    del fixture. Limpiamos products + import_runs antes de cada test.
    """
    from sqlalchemy import text

    await db_session.execute(text("DELETE FROM product_translations;"))
    await db_session.execute(text("DELETE FROM product_assets;"))
    # products tiene trigger anti-DELETE — desactivamos para tests.
    await db_session.execute(
        text("ALTER TABLE products DISABLE TRIGGER trg_products_no_hard_delete;")
    )
    await db_session.execute(text("DELETE FROM products;"))
    await db_session.execute(
        text("ALTER TABLE products ENABLE TRIGGER trg_products_no_hard_delete;")
    )
    await db_session.execute(text("DELETE FROM import_runs;"))
    await db_session.commit()
    yield


# ---------------------------------------------------------------------------
# Synthetic xlsx generator
# ---------------------------------------------------------------------------
def _build_synthetic_pim_xlsx(
    rows: list[tuple[Any, ...]] | None = None,
    *,
    bad_header: bool = False,
) -> bytes:
    """Construye un xlsx con el header canonico + filas dadas.

    Args:
        rows: lista de tuples (17 columnas). Si None, default 5 filas validas.
        bad_header: si True, escribe un header invalido para tests negativos.
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if bad_header:
        ws.append(["WRONG_HEADER"] * len(EXPECTED_HEADERS))
    else:
        ws.append(list(EXPECTED_HEADERS))

    if rows is None:
        rows = [
            (
                "MT-T01",  # SKU
                "84818019",  # Intrastat
                "Test Valve T01",  # ERP name → name_en
                "1234567890123",  # individual EAN
                "1.5",  # weight unit (gross kg, va a specs)
                "1.2",  # net weight unit (peso neto canonico)
                "100",  # High mm
                "50",  # Wide mm
                "30",  # Deep mm
                "1234567890124",  # EAN BOX
                "12",  # qty x box
                "10",  # Alto caja cm
                "8",  # Ancho caja cm
                "20",  # Largo caja cm
                "1234567890125",  # EAN INNER BOX
                "120",  # MOQ
                "60",  # X PALLET
            ),
            (
                "MT-T02",
                "84818020",
                "Test Valve T02",
                "2234567890123",
                "2.0",
                "1.7",
                "150",
                "60",
                "40",
                "2234567890124",
                "6",
                "12",
                "10",
                "25",
                "2234567890125",
                "60",
                "30",
            ),
            (
                "MT-T03",
                None,
                "Test Valve T03",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
            (
                # Numéricos como string — debe castear OK.
                "MT-T04",
                "84818021",
                "Test Valve T04",
                "3234567890123",
                "0.5",
                "0.4",
                "75",
                "40",
                "20",
                None,
                "24",
                "5",
                "5",
                "10",
                None,
                None,
                None,
            ),
            (
                "MT-T05",
                "84818022",
                "Test Valve T05",
                None,
                None,
                "0.9",
                "120",
                "50",
                "35",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        ]

    for row in rows:
        ws.append(list(row))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_xlsx_to_tmp(tmp_path, xlsx_bytes: bytes) -> str:
    """Escribe el xlsx a un tmp path y devuelve el path str."""
    target = tmp_path / "test_pim.xlsx"
    target.write_bytes(xlsx_bytes)
    return str(target)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def queued_run(db_session: AsyncSession) -> ImportRun:
    """Crea un ImportRun en estado 'queued' (estado pre-task)."""
    run = ImportRun(
        import_type="pim",
        source_filename="test_pim.xlsx",
        source_storage_path=None,
        status="queued",
    )
    db_session.add(run)
    await db_session.commit()
    return run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_pim_importer_inserts_5_rows(
    db_session: AsyncSession, tmp_path, queued_run: ImportRun
) -> None:
    """Con 5 filas válidas, debe insertar 5 productos y status=completed."""
    xlsx_bytes = _build_synthetic_pim_xlsx()
    path = _write_xlsx_to_tmp(tmp_path, xlsx_bytes)

    importer = PimImporter(
        session=db_session,
        source_path=path,
        run_id=queued_run.id,
        actor_id=None,
    )
    run = await importer.run()
    await db_session.refresh(run)

    assert run.status == "completed", run.errors
    assert run.total_rows == 5
    assert run.inserted_rows == 5
    assert run.updated_rows == 0
    assert run.error_rows == 0

    # Productos en BD
    from sqlalchemy import select

    result = await db_session.execute(select(Product).order_by(Product.sku))
    products = list(result.scalars().all())
    skus = [p.sku for p in products]
    assert "MT-T01" in skus
    assert "MT-T02" in skus
    # Verifica casts (Decimal/JSONB).
    p1 = next(p for p in products if p.sku == "MT-T01")
    assert p1.name_en == "Test Valve T01"
    assert p1.intrastat_code == "84818019"
    # dimensions JSONB.
    assert p1.dimensions.get("high_mm") == "100"
    # packaging JSONB.
    assert p1.packaging.get("qty_per_box") == 12
    # cm→mm conversion.
    assert p1.packaging.get("box_high_mm") == "100"  # 10 cm x 10 = 100 mm


async def test_pim_importer_idempotent_on_rerun(
    db_session: AsyncSession, tmp_path, queued_run: ImportRun
) -> None:
    """Re-correr el mismo PIM no duplica filas (UPSERT por SKU)."""
    xlsx_bytes = _build_synthetic_pim_xlsx()
    path = _write_xlsx_to_tmp(tmp_path, xlsx_bytes)

    importer1 = PimImporter(
        session=db_session,
        source_path=path,
        run_id=queued_run.id,
        actor_id=None,
    )
    await importer1.run()

    # Segundo run con run_id distinto — mismos datos.
    run2 = ImportRun(
        import_type="pim",
        source_filename="test_pim.xlsx",
        status="queued",
    )
    db_session.add(run2)
    await db_session.commit()

    importer2 = PimImporter(
        session=db_session,
        source_path=path,
        run_id=run2.id,
        actor_id=None,
    )
    run_result = await importer2.run()
    await db_session.refresh(run_result)

    # Mismos datos → 0 inserts, 0 updates (no diff), 5 skipped.
    assert run_result.inserted_rows == 0
    assert run_result.updated_rows == 0
    assert run_result.skipped_rows == 5

    # Verifica conteo final de productos no se duplicó.
    from sqlalchemy import func, select

    count = (await db_session.execute(select(func.count(Product.sku)))).scalar_one()
    assert count == 5


async def test_pim_importer_skips_empty_rows(
    db_session: AsyncSession, tmp_path, queued_run: ImportRun
) -> None:
    """Filas totalmente vacias se cuentan como skipped, no error."""
    rows = [
        (
            "MT-E01",
            "84818019",
            "ERP E01",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),  # vacia
        (
            "MT-E02",
            "84818020",
            "ERP E02",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
    ]
    xlsx_bytes = _build_synthetic_pim_xlsx(rows=rows)
    path = _write_xlsx_to_tmp(tmp_path, xlsx_bytes)

    importer = PimImporter(
        session=db_session,
        source_path=path,
        run_id=queued_run.id,
        actor_id=None,
    )
    run = await importer.run()
    await db_session.refresh(run)

    assert run.inserted_rows == 2
    assert run.skipped_rows >= 1  # fila vacia
    assert run.error_rows == 0


async def test_pim_importer_header_mismatch(
    db_session: AsyncSession, tmp_path, queued_run: ImportRun
) -> None:
    """Header incorrecto → status=failed sin tocar productos."""
    xlsx_bytes = _build_synthetic_pim_xlsx(bad_header=True)
    path = _write_xlsx_to_tmp(tmp_path, xlsx_bytes)

    importer = PimImporter(
        session=db_session,
        source_path=path,
        run_id=queued_run.id,
        actor_id=None,
    )
    run = await importer.run()
    await db_session.refresh(run)

    assert run.status == "failed"
    assert run.errors and "Header mismatch" in run.errors[0]["error"]
    # Productos NO se crean.
    from sqlalchemy import func, select

    count = (await db_session.execute(select(func.count(Product.sku)))).scalar_one()
    assert count == 0


async def test_pim_importer_numeric_strings_cast_ok(
    db_session: AsyncSession, tmp_path, queued_run: ImportRun
) -> None:
    """Numéricos como strings ('250.0', '12') se castean OK sin error."""
    rows = [
        (
            "MT-NUM01",
            "84818019",
            "Numeric String Test",
            "1234567890123",
            "1.5",  # str→Decimal
            "1.2",
            "100",  # str→Decimal
            "50",
            "30",
            None,
            "12",  # str→int
            "10",  # str→cm→mm Decimal
            "8",
            "20",
            None,
            "120",
            "60",
        ),
    ]
    xlsx_bytes = _build_synthetic_pim_xlsx(rows=rows)
    path = _write_xlsx_to_tmp(tmp_path, xlsx_bytes)

    importer = PimImporter(
        session=db_session,
        source_path=path,
        run_id=queued_run.id,
        actor_id=None,
    )
    run = await importer.run()
    await db_session.refresh(run)

    assert run.inserted_rows == 1
    assert run.error_rows == 0

    from sqlalchemy import select

    p = (await db_session.execute(select(Product).where(Product.sku == "MT-NUM01"))).scalar_one()
    assert p.packaging.get("qty_per_box") == 12  # int casted from "12"
    assert p.dimensions.get("high_mm") == "100"  # decimal stringified
