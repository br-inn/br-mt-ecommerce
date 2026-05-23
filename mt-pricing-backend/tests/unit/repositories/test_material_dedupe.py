"""Stage 3 / Wave 11 follow-up — invariantes post-migración 047 materials_dedupe.

Verifica las 3 invariantes que la migración debe garantizar tras
``alembic upgrade head``:

1. **0 productos** apuntan a un ``materials.active = false``.
2. **Exactamente 8** duplicados EN remapeados quedan ``active = false``.
3. **Todos** los materials ``active = true`` tienen ``family_kind`` seteado.

Estos tests verifican el **estado** de la BD tras correr todas las
migraciones (`alembic upgrade head`) — son post-migration assertions
contra la BD apuntada por ``DATABASE_URL`` (Postgres dev local cuando se
corre desde el container ``mt-backend``).

Cuando ``DATABASE_URL`` no está disponible (p. ej. CI sin BD lista) el
módulo se *skipea* automáticamente para no romper la suite.
"""

from __future__ import annotations

import os

import pytest

# Saltamos el módulo entero si no hay DATABASE_URL — evita pelearse con
# testcontainers / docker-in-docker en entornos donde la fixture
# `postgres_container` no aplica. La invariante se valida contra la BD
# dev local apuntada por DATABASE_URL en el container `mt-backend`.
_DB_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not _DB_URL,
    reason="DATABASE_URL no setteado — test post-migración requiere BD migrada",
)


_REMAPPED_EN_CODES = (
    "brass",
    "cast_iron",
    "stainless_steel",
    "stainless_steel_304",
    "stainless_steel_316l",
    "galvanised_steel",
    "pvc",
    "pvc-u",
)

_RENAMED_IN_PLACE = {
    "copper": ("Cobre", "metal"),
    "multilayer": ("Multicapa", "composite"),
    "polyethylene": ("Polietileno", "polymer"),
    "pe_xa": ("PE-Xa", "polymer"),
    "polyamide": ("Poliamida", "polymer"),
    "abs": ("ABS", "polymer"),
    "nbr": ("NBR", "polymer"),
    "epdm": ("EPDM", "polymer"),
}


def _sync_url() -> str:
    """URL síncrona derivada de ``DATABASE_URL`` para SQLAlchemy estándar.

    En la suite el container expone la URL con driver ``+asyncpg``; aquí
    queremos un engine síncrono → reemplazamos por ``+psycopg`` (psycopg3,
    que es lo que ya viene en la imagen).
    """
    raw = os.environ["DATABASE_URL"]
    return raw.replace("+asyncpg", "+psycopg")


@pytest.fixture(scope="module")
def alembic_sync_url() -> str:
    return _sync_url()


def test_no_products_point_to_inactive_materials(alembic_sync_url: str) -> None:
    """Invariante 1: 0 productos apuntan a materials con active=false.

    Se ejecuta directamente contra la BD migrada (read-only). Tras la
    migración 047 todos los productos que apuntaban a duplicados EN
    fueron remapeados a sus canónicos ES, por lo que el JOIN con
    ``materials.active = false`` debe devolver 0.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(alembic_sync_url)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS n
                    FROM products p
                    JOIN materials m ON m.id = p.material_id
                    WHERE m.active = false;
                    """
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert count == 0, (
        f"Esperado 0 productos apuntando a materials inactivos, encontrados {count}. "
        "La migración 047 debe remapear todos los productos desde duplicados EN "
        "hacia canónicos ES antes de desactivar."
    )


def test_exactly_eight_en_duplicates_inactive(alembic_sync_url: str) -> None:
    """Invariante 2: exactamente 8 duplicados EN tienen active=false."""
    from sqlalchemy import create_engine, text

    engine = create_engine(alembic_sync_url)
    try:
        with engine.connect() as conn:
            inactive_codes = {
                row[0]
                for row in conn.execute(
                    text("SELECT code FROM materials WHERE active = false ORDER BY code;")
                ).all()
            }
    finally:
        engine.dispose()

    assert inactive_codes == set(_REMAPPED_EN_CODES), (
        f"Esperados exactamente estos 8 códigos EN inactivos: "
        f"{sorted(_REMAPPED_EN_CODES)}; encontrados: {sorted(inactive_codes)}."
    )
    assert len(inactive_codes) == 8


def test_all_active_materials_have_family_kind(alembic_sync_url: str) -> None:
    """Invariante 3: todo material active=true tiene family_kind != NULL."""
    from sqlalchemy import create_engine, text

    engine = create_engine(alembic_sync_url)
    try:
        with engine.connect() as conn:
            missing = conn.execute(
                text(
                    """
                    SELECT code FROM materials
                    WHERE active = true
                      AND (family_kind IS NULL OR btrim(family_kind) = '')
                    ORDER BY code;
                    """
                )
            ).all()
    finally:
        engine.dispose()

    assert missing == [], (
        f"Esperado 0 materials activos sin family_kind, encontrados: {[row[0] for row in missing]}."
    )


def test_renamed_in_place_have_spanish_names(alembic_sync_url: str) -> None:
    """Sanity check del rename in place: name ES + family_kind correctos."""
    from sqlalchemy import create_engine, text

    engine = create_engine(alembic_sync_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT code, name, family_kind
                    FROM materials
                    WHERE code = ANY(:codes)
                    ORDER BY code;
                    """
                ),
                {"codes": list(_RENAMED_IN_PLACE.keys())},
            ).all()
    finally:
        engine.dispose()

    by_code = {row[0]: (row[1], row[2]) for row in rows}
    for code, (expected_name, expected_kind) in _RENAMED_IN_PLACE.items():
        assert code in by_code, f"material {code!r} no encontrado tras 047"
        actual_name, actual_kind = by_code[code]
        assert actual_name == expected_name, (
            f"{code}: esperado name={expected_name!r}, actual {actual_name!r}"
        )
        assert actual_kind == expected_kind, (
            f"{code}: esperado family_kind={expected_kind!r}, actual {actual_kind!r}"
        )
