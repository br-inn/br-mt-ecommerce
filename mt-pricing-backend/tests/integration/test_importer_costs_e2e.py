"""Integration test E2E del importer costos (US-1A-06-02).

Skip-by-default — depende del merge de US-1A-04-03 (POST /costs API real)
que entrega Agent F. Cuando merge, basta con eliminar el `pytest.skip`.
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(reason="depends on costs API merge (US-1A-04-03 / Agent F)"),
]


async def test_full_preview_apply_pipeline_against_real_db() -> None:
    """Ejercicio end-to-end:
    1. Sube un xlsx de costos contra ``POST /imports/costs/preview``.
    2. Verifica summary, orphan_report.
    3. Llama ``POST /imports/costs/{id}/apply`` y comprueba creación de filas
       en ``costs`` table.
    4. ``GET /imports/costs/{id}/report`` retorna detalles coherentes.

    Este test se activará cuando el ``CostService.create_cost`` real esté
    disponible y cuando la migración 020 (translation workflow) deje la cadena
    Alembic ejecutable hasta head.
    """
    raise NotImplementedError("activar al merge de US-1A-04-03")
