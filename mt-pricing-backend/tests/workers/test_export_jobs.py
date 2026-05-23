"""Tests US-1B-04-05 — capture_last_good_exports job diario.

Suite de integración contra Postgres efímero (testcontainers).

Tests:
1. test_capture_creates_last_good    — 2 exports completed → upserta el más reciente.
2. test_capture_skips_failed         — exports failed/pending no se capturan.
3. test_capture_upserts_on_rerun     — segunda ejecución actualiza, no duplica.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _migrated_db(postgres_container: str) -> str:
    """Aplica alembic upgrade head y devuelve la URL sync."""
    from alembic import command
    from alembic.config import Config

    sync_url = os.environ["ALEMBIC_DATABASE_URL"]
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")
    return sync_url


@pytest.fixture()
def sync_engine(_migrated_db: str):
    """Engine sincrónico con auto-rollback al final del test."""
    engine = create_engine(_migrated_db, future=True)
    yield engine
    engine.dispose()


def _insert_manifest(
    conn,
    channel_code: str,
    scheme_code: str,
    status: str,
    rows_exported: int,
    file_ref: str,
    offset_seconds: int = 0,
) -> str:
    """Inserta una fila en exports_manifest y devuelve su id."""
    manifest_id = str(uuid.uuid4())
    created_at = datetime.now(tz=timezone.utc) - timedelta(seconds=offset_seconds)
    conn.execute(
        text(
            """
            INSERT INTO exports_manifest
                (id, channel_code, scheme_code, status, rows_exported, rows_blocked,
                 file_ref, generated_by, created_at, updated_at)
            VALUES
                (:id, :channel_code, :scheme_code, :status, :rows_exported, 0,
                 :file_ref, NULL, :created_at, :created_at)
            """
        ),
        {
            "id": manifest_id,
            "channel_code": channel_code,
            "scheme_code": scheme_code,
            "status": status,
            "rows_exported": rows_exported,
            "file_ref": file_ref,
            "created_at": created_at,
        },
    )
    return manifest_id


def _count_last_good(conn, channel_code: str, scheme_code: str) -> int:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM last_good_exports WHERE channel_code = :ch AND scheme_code = :sc"
        ),
        {"ch": channel_code, "sc": scheme_code},
    ).scalar()
    return int(row)


def _fetch_last_good(conn, channel_code: str, scheme_code: str) -> dict | None:
    row = (
        conn.execute(
            text("SELECT * FROM last_good_exports WHERE channel_code = :ch AND scheme_code = :sc"),
            {"ch": channel_code, "sc": scheme_code},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_capture_creates_last_good(sync_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """2 exports completed para el mismo canal/scheme → captura el más reciente."""
    from app.workers import export_jobs

    monkeypatch.setattr(
        export_jobs.settings,
        "ALEMBIC_DATABASE_URL",
        str(sync_engine.url),
    )

    channel = "AMAZON_UAE"
    scheme = "DEFAULT"

    with sync_engine.begin() as conn:
        # Más antiguo (offset 120s)
        _insert_manifest(conn, channel, scheme, "completed", 50, "file_old.csv", offset_seconds=120)
        # Más reciente (offset 0s)
        newer_id = _insert_manifest(
            conn, channel, scheme, "completed", 80, "file_new.csv", offset_seconds=0
        )

    result = export_jobs._run_capture(str(sync_engine.url))

    assert result["upserted"] >= 1

    with sync_engine.connect() as conn:
        row = _fetch_last_good(conn, channel, scheme)

    assert row is not None, "Debe existir una fila en last_good_exports"
    assert str(row["export_manifest_id"]) == newer_id, "Debe apuntar al export más reciente"
    assert row["rows_exported"] == 80
    assert row["file_ref"] == "file_new.csv"


@pytest.mark.integration
def test_capture_skips_failed(sync_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exports con status failed o pending NO deben aparecer en last_good_exports."""
    from app.workers import export_jobs

    monkeypatch.setattr(
        export_jobs.settings,
        "ALEMBIC_DATABASE_URL",
        str(sync_engine.url),
    )

    channel = "NOON_UAE"
    scheme = "PROMO"

    with sync_engine.begin() as conn:
        _insert_manifest(conn, channel, scheme, "failed", 10, "failed.csv")
        _insert_manifest(conn, channel, scheme, "pending", 0, "pending.csv")

    export_jobs._run_capture(str(sync_engine.url))

    with sync_engine.connect() as conn:
        count = _count_last_good(conn, channel, scheme)

    assert count == 0, "No deben capturarse exports failed/pending"


@pytest.mark.integration
def test_capture_upserts_on_rerun(sync_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Segunda ejecución actualiza la fila existente en lugar de duplicar."""
    from app.workers import export_jobs

    monkeypatch.setattr(
        export_jobs.settings,
        "ALEMBIC_DATABASE_URL",
        str(sync_engine.url),
    )

    channel = "CARREFOUR_UAE"
    scheme = "B2C"

    with sync_engine.begin() as conn:
        first_id = _insert_manifest(
            conn, channel, scheme, "completed", 30, "first.csv", offset_seconds=200
        )

    # Primera ejecución
    export_jobs._run_capture(str(sync_engine.url))

    with sync_engine.begin() as conn:
        second_id = _insert_manifest(
            conn, channel, scheme, "completed", 99, "second.csv", offset_seconds=0
        )

    # Segunda ejecución
    export_jobs._run_capture(str(sync_engine.url))

    with sync_engine.connect() as conn:
        count = _count_last_good(conn, channel, scheme)
        row = _fetch_last_good(conn, channel, scheme)

    assert count == 1, f"Debe haber exactamente 1 fila (upsert), encontradas: {count}"
    assert str(row["export_manifest_id"]) == second_id, "Debe actualizarse al export más reciente"
    assert row["rows_exported"] == 99
    assert row["file_ref"] == "second.csv"
