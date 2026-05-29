from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.importer.importer_service import ImporterService

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config  # noqa: I001
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


def _make_user() -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "actor@example.com"
    return u


_NS = "https://mtme-api/schemas/articulos/v1"
_XML = (f'<catalog xmlns="{_NS}"><article><sku>MT-XML-1</sku>'
        f"<name_en>XML Valve</name_en><family>ball_valve</family>"
        f"<dn>25</dn></article></catalog>")


async def test_preview_accepts_xml(db_session: AsyncSession) -> None:
    svc = ImporterService(db_session)
    state = await svc.preview(
        file_bytes=_XML.encode("utf-8"),
        filename="articulos.xml",
        actor=_make_user(),
        type_="pim",
    )
    assert state.status == "preview_ready"
    assert state.summary["total"] == 1
    assert state.summary["creates"] == 1
