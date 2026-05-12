"""Integration tests — seed_kg_materials.py contra Neo4j real.

Verifica:
- El seed crea nodos Material en Neo4j.
- El seed es idempotente (segunda ejecución no duplica nodos).
- --dry-run no escribe nada en Neo4j.

Marca: @pytest.mark.neo4j_real — sólo corre cuando hay Neo4j disponible.
Requiere el fixture `neo4j_driver` (scope=session) de conftest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Ruta al script relativa al root del proyecto (un nivel sobre mt-pricing-backend)
_SCRIPT = str(
    Path(__file__).parents[5] / "scripts" / "seed_kg_materials.py"
)


@pytest.mark.neo4j_real
class TestKgSeed:
    def test_seed_creates_nodes(self, neo4j_driver) -> None:  # noqa: ANN001
        """Seed crea nodos Material en Neo4j."""
        subprocess.run([sys.executable, _SCRIPT], check=True)
        with neo4j_driver.session() as s:
            result = s.run("MATCH (n:Material) RETURN count(n) AS cnt").single()
            assert result["cnt"] > 500

    def test_seed_is_idempotent(self, neo4j_driver) -> None:  # noqa: ANN001
        """Segunda ejecución no duplica nodos."""
        subprocess.run([sys.executable, _SCRIPT], check=True)
        with neo4j_driver.session() as s:
            count1 = s.run("MATCH (n:Material) RETURN count(n) AS cnt").single()["cnt"]
        subprocess.run([sys.executable, _SCRIPT], check=True)
        with neo4j_driver.session() as s:
            count2 = s.run("MATCH (n:Material) RETURN count(n) AS cnt").single()["cnt"]
        assert count1 == count2

    def test_dry_run_no_writes(self, neo4j_driver) -> None:  # noqa: ANN001
        """--dry-run no escribe nada en Neo4j."""
        with neo4j_driver.session() as s:
            count_before = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        subprocess.run([sys.executable, _SCRIPT, "--dry-run"], check=True)
        with neo4j_driver.session() as s:
            count_after = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        assert count_before == count_after
