"""Guard: ``infra/scripts/migrate.sh`` debe aplicar migraciones y verificarlas.

Regresión que motiva este test: el script era un *placeholder* no-op
(``echo`` + ``exit 0``), por lo que el deploy NO aplicaba migraciones y la DB
quedaba desincronizada del código (alembic_version marcada en una revisión cuyo
DDL nunca se aplicó). Estos tests evitan que vuelva a ser un placeholder y exigen
la verificación post-upgrade (``alembic check``), que detecta el caso
"stamped pero no aplicado".

Son tests puros (leen el script) → corren en cualquier entorno de CI sin DB.
"""

from __future__ import annotations

import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_MIGRATE_SH = _REPO_ROOT / "infra" / "scripts" / "migrate.sh"


def _script_text() -> str:
    assert _MIGRATE_SH.is_file(), f"no existe {_MIGRATE_SH}"
    return _MIGRATE_SH.read_text(encoding="utf-8")


def test_migrate_script_exists() -> None:
    assert _MIGRATE_SH.is_file(), f"no existe {_MIGRATE_SH}"


def test_migrate_script_runs_alembic_upgrade() -> None:
    text = _script_text()
    assert "alembic" in text, "migrate.sh debe invocar alembic"
    assert '"${ALEMBIC[@]}" "${ACTION}" "${TARGET}"' in text, (
        "migrate.sh debe ejecutar 'alembic <action> <target>' realmente, "
        "no sólo mencionarlo en comentarios"
    )


def test_migrate_script_verifies_applied_schema() -> None:
    text = _script_text()
    assert '"${ALEMBIC[@]}" check' in text, (
        "migrate.sh debe verificar el schema con 'alembic check' tras el upgrade "
        "(detecta el caso stamped-pero-no-aplicado)"
    )


def test_migrate_script_is_not_noop_placeholder() -> None:
    text = _script_text()
    assert "placeholder — would run" not in text, (
        "migrate.sh sigue siendo el placeholder no-op — el deploy no aplicaría migraciones"
    )
