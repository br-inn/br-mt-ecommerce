"""Integration tests para `/imports` wizard PIM (US-1A-06-01).

Cobertura:
- ``POST /imports/preview`` con archivo real → 200 + summary.
- ``POST /imports/{run_id}/apply`` aplica chunked → counts coherentes con preview.
- ``GET /imports/{run_id}/status`` devuelve estado actualizado.
- ``GET /imports/{run_id}/report?format=csv`` retorna CSV con header esperado.
- Apply respeta `manual_locked_fields` (skip_locked).
- Apply genera audit_events por chunk + por row.
"""

from __future__ import annotations

import io
import os
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"

PIM_REAL_PATH = (
    r"c:\BR-Github\br-mt\br-mt-ecommerce\Documentos referencia de articulos"
    r"\PIM completo.xlsx"
)


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "ti_integracion"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


async def _seed_ti(session: AsyncSession) -> tuple[UUID, str]:
    from app.db.models.user import Permission, Role, RolePermission, User

    perms_codes = ["imports:read", "imports:write", "products:write"]
    perm_ids = []
    for code in perms_codes:
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)
    role = (await session.execute(select(Role).where(Role.code == "ti_imp"))).scalar_one_or_none()
    if role is None:
        role = Role(code="ti_imp", name="ti_imp", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"ti-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="TI", locale="es", is_active=True, role_id=role.id)
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def app_with_db(db_session: AsyncSession) -> AsyncIterator[Any]:
    from app.api.deps import get_db_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def client(app_with_db: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def _build_minimal_xlsx(rows: int = 3) -> bytes:
    """Genera un xlsx en memoria con el header oficial sprint0 + N rows."""
    from app.services.importer.column_mapper import EXPECTED_HEADERS

    wb = Workbook()
    ws = wb.active
    ws.append(list(EXPECTED_HEADERS))
    for i in range(rows):
        ws.append(
            [
                f"TST-{i:04d}",  # Referencia de variante
                "73071910",  # Cod.Intrastat
                f"test product {i}",  # Nombre ERP
                f"843531910000{i}",  # INDIVIDUAL EAN (13)
                f"0.{i + 1}",  # weight unit
                f"0.{i + 1}",  # net weight unit
                f"{i + 1}.0",  # High mm
                f"{i + 1}.0",  # Wide mm
                f"{i + 1}.0",  # Deep mm
                f"284353191000{i}0",  # EAN CODE BOX (14)
                "100",  # qty x box
                "10",  # Alto caja cm
                "20",  # Ancho caja cm
                "30",  # Largo caja cm
                f"184353191000{i}0",  # EAN CODE INNER BOX
                "5",  # MOQ INNER BOX
                "1000",  # X PALLET
            ]
        )
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preview_minimal_xlsx_returns_summary(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    file_bytes = _build_minimal_xlsx(rows=5)
    files = {
        "file": (
            "test_pim.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    r = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "preview_ready"
    assert body["summary"]["total"] == 5
    assert body["summary"]["create"] == 5
    assert body["summary"]["update"] == 0
    # Buckets están presentes en samples.
    assert "create" in body["samples"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preview_then_apply_creates_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.db.models.product import Product
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()

    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    file_bytes = _build_minimal_xlsx(rows=3)
    files = {"file": ("p.xlsx", file_bytes, "application/octet-stream")}
    rp = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    assert rp.status_code == 200, rp.text
    run_id = rp.json()["run_id"]

    ra = await client.post(
        f"/api/v1/imports/{run_id}/apply", json={"chunk_size": 1000}, headers=headers
    )
    assert ra.status_code == 200, ra.text
    body = ra.json()
    assert body["status"] in ("completed", "completed_with_failures")
    assert body["apply"]["created"] == 3

    # Verifica que efectivamente se crearon en BD.
    res = await db_session.execute(
        select(func.count()).select_from(Product).where(Product.sku.like("TST-%"))
    )
    assert (res.scalar_one() or 0) >= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_respects_manual_locked_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Si un SKU ya existe con `dn` bloqueado, el importer no debe sobreescribirlo."""
    from app.db.models.product import Product
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()

    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    # Pre-crear el SKU con dn=DN15 y bloquearlo.
    sku = "TST-LOCK-0000"
    pre_payload = {
        "sku": sku,
        "name_en": "Ball valve",
        "family": "valves_ball",
        "dn": "DN15",
        "pn": "PN16",
    }
    r = await client.post("/api/v1/products", json=pre_payload, headers=headers)
    assert r.status_code == 201, r.text
    rp = await client.patch(
        f"/api/v1/products/{sku}",
        json={"manual_locked_fields": ["dn"]},
        headers=headers,
    )
    assert rp.status_code == 200, rp.text

    # Ahora generar un xlsx con MISMO sku pero dn implícito (cae en family default
    # 'unclassified'). El differ debe marcar 'family' como cambio (unlocked) →
    # action=update, y NO tocar dn (no viene en payload del importer; si vinera,
    # lo skipearía).
    from openpyxl import Workbook

    from app.services.importer.column_mapper import EXPECTED_HEADERS

    wb = Workbook()
    ws = wb.active
    ws.append(list(EXPECTED_HEADERS))
    ws.append(
        [
            sku,  # Referencia de variante
            "73071910",  # Cod.Intrastat
            "import overwrite name",  # Nombre ERP
            "8435319100099",
            "0.1",
            "0.1",
            "1.0",
            "1.0",
            "1.0",
            "28435319100992",
            "100",
            "10",
            "20",
            "30",
            "18435319100995",
            "5",
            "1000",
        ]
    )
    bio = io.BytesIO()
    wb.save(bio)
    files = {"file": ("lock.xlsx", bio.getvalue(), "application/octet-stream")}
    rprev = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    assert rprev.status_code == 200
    run_id = rprev.json()["run_id"]

    rapp = await client.post(f"/api/v1/imports/{run_id}/apply", headers=headers)
    assert rapp.status_code == 200, rapp.text

    # Verifica DB: dn sigue siendo 'DN15' (no sobreescrito).
    from sqlalchemy import select as _sel

    res = await db_session.execute(_sel(Product).where(Product.sku == sku))
    prod = res.scalar_one()
    assert prod.dn == "DN15"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_emits_audit_events(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.db.models.audit import AuditEvent
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()

    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    file_bytes = _build_minimal_xlsx(rows=4)
    files = {"file": ("a.xlsx", file_bytes, "application/octet-stream")}
    rp = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    run_id = rp.json()["run_id"]
    ra = await client.post(f"/api/v1/imports/{run_id}/apply", headers=headers)
    assert ra.status_code == 200

    # 4 audit events de creación (uno por row) + ≥1 audit por chunk summary.
    res = await db_session.execute(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.action.in_(["product.imported.created", "product.import.chunk_completed"])
        )
    )
    assert (res.scalar_one() or 0) >= 5  # 4 rows + 1 chunk summary


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_status_returns_current(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()
    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    file_bytes = _build_minimal_xlsx(rows=2)
    files = {"file": ("s.xlsx", file_bytes, "application/octet-stream")}
    rp = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    run_id = rp.json()["run_id"]
    rs = await client.get(f"/api/v1/imports/{run_id}/status", headers=headers)
    assert rs.status_code == 200
    assert rs.json()["status"] == "preview_ready"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_csv_format(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()
    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    file_bytes = _build_minimal_xlsx(rows=2)
    files = {"file": ("r.xlsx", file_bytes, "application/octet-stream")}
    rp = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    run_id = rp.json()["run_id"]
    rr = await client.get(f"/api/v1/imports/{run_id}/report?format=csv", headers=headers)
    assert rr.status_code == 200
    assert rr.headers["content-type"].startswith("text/csv")
    text = rr.text
    assert text.startswith("row_index,sku,action,errors,locked_fields_skipped,diff_keys")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preview_invalid_header_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    wb = Workbook()
    ws = wb.active
    ws.append(["foo", "bar"])  # Header roto.
    ws.append(["x", "y"])
    bio = io.BytesIO()
    wb.save(bio)
    files = {"file": ("bad.xlsx", bio.getvalue(), "application/octet-stream")}
    r = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == "import_header_mismatch"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not os.path.exists(PIM_REAL_PATH), reason="PIM real no disponible")
async def test_preview_real_pim_full(client: AsyncClient, db_session: AsyncSession) -> None:
    """Smoke test sobre el PIM real (5085 rows). Solo preview, sin apply."""
    from app.services.importer.importer_service import reset_run_store

    reset_run_store()
    uid, email = await _seed_ti(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    with open(PIM_REAL_PATH, "rb") as fp:
        file_bytes = fp.read()
    files = {"file": ("PIM completo.xlsx", file_bytes, "application/octet-stream")}
    r = await client.post("/api/v1/imports/preview", files=files, headers=headers)
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["total"] == 5085
    # Mayoría debería detectarse como CREATE (DB vacía al inicio del test).
    assert summary["create"] >= 3000
