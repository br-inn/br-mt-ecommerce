"""Tests de la capa de datos (SQLAlchemy + Alembic + Supabase migrations).

Convenciones:
- Tests unit puros (import-only) NO requieren testcontainers; viven aquí
  marcados con `pytest.mark.unit`.
- Tests que requieren BD real (Postgres efímero via testcontainers) se marcan
  con `pytest.mark.integration` y consumen los fixtures de `tests/conftest.py`
  (`postgres_container`, `db_engine`, `db_session`).
"""
