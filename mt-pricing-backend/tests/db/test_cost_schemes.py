"""US-1A-04-01 — DoD: 5 cost schemes seeded con cost_components_template.

Valida:
- Las 5 filas (FBA, FBM, DIRECT_B2C, DIRECT_B2B, MARKETPLACE) están seeded.
- `cost_components_template->>'required'` contiene los componentes esperados
  por cada esquema (lista exacta de la spec).
- CHECK ck_schemes_code rechaza códigos fuera del enum.
- Insertar duplicado falla por PK.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


# Espejo de _SCHEMES_SEED en la migración.
_EXPECTED_COMPONENTS = {
    "FBA": ["fob", "freight", "customs", "fba_fees", "payment_fees"],
    "FBM": ["fob", "freight", "customs", "fbm_fees", "payment_fees"],
    "DIRECT_B2C": ["fob", "freight", "customs", "payment_fees", "marketing"],
    "DIRECT_B2B": ["fob", "freight", "customs", "payment_fees"],
    "MARKETPLACE": [
        "fob",
        "freight",
        "customs",
        "marketplace_fees",
        "payment_fees",
        "marketing",
    ],
}


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_five_schemes_seeded(db_session: "AsyncSession") -> None:
    """SELECT * FROM schemes — exactamente 5 filas."""
    rows = await db_session.execute(text("SELECT code FROM schemes ORDER BY code;"))
    codes = [r[0] for r in rows.all()]
    assert codes == ["DIRECT_B2B", "DIRECT_B2C", "FBA", "FBM", "MARKETPLACE"]


@pytest.mark.parametrize("scheme_code,expected", list(_EXPECTED_COMPONENTS.items()))
async def test_scheme_template_components(
    db_session: "AsyncSession", scheme_code: str, expected: list[str]
) -> None:
    """Cada esquema tiene su `cost_components_template.required` esperado."""
    row = await db_session.execute(
        text(
            "SELECT cost_components_template->'required' FROM schemes "
            "WHERE code = :code;"
        ).bindparams(code=scheme_code)
    )
    raw = row.scalar_one()
    # JSONB array → Python list (asyncpg deserializa a list).
    assert raw == expected, f"{scheme_code}: expected {expected}, got {raw}"


async def test_scheme_code_check_constraint(db_session: "AsyncSession") -> None:
    """CHECK ck_schemes_code rechaza valores fuera del enum."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO schemes (code, name) VALUES ('INVALID_SCHEME', 'Bad');"
            )
        )
        await db_session.flush()


async def test_scheme_pk_unique(db_session: "AsyncSession") -> None:
    """Duplicar code='FBA' falla por PK."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("INSERT INTO schemes (code, name) VALUES ('FBA', 'Dup');")
        )
        await db_session.flush()
