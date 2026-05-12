"""Seed script — Knowledge Graph de Compatibilidad de Materiales.

Pobla Neo4j con nodos Material/Standard y edges COMPATIBLE_WITH
desde un CSV. Idempotente: usa MERGE en todos los upserts.

Uso:
    python scripts/seed_kg_materials.py [--dry-run] [--csv PATH]

Exit codes:
    0  — éxito (o dry-run OK)
    1  — error
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:17687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "devpassword")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

DEFAULT_CSV = Path(__file__).parent / "seed_data" / "kg_materials_seed.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("seed_kg_materials")

# ---------------------------------------------------------------------------
# Cypher — constraints
# ---------------------------------------------------------------------------
CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Material) REQUIRE n.primary_key IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Standard) REQUIRE n.primary_key IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Supplier) REQUIRE n.primary_key IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product) REQUIRE n.primary_key IS UNIQUE",
]

# ---------------------------------------------------------------------------
# Cypher — upsert edge
# ---------------------------------------------------------------------------
MERGE_COMPAT = """
MERGE (a:Material {primary_key: $mat_a})
  ON CREATE SET a.name = $mat_a, a.category = $cat_a
MERGE (b:Material {primary_key: $mat_b})
  ON CREATE SET b.name = $mat_b, b.category = $cat_b
MERGE (std:Standard {primary_key: $standard})
  ON CREATE SET std.name = $standard
MERGE (a)-[r:COMPATIBLE_WITH {standard: $standard}]->(b)
  ON CREATE SET r.pressure_bar = $pressure,
               r.temperature_range = $temp,
               r.confidence = $confidence
  ON MATCH SET  r.confidence = $confidence
"""


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _infer_category(material: str) -> str:
    """Categoría heurística por nombre de material."""
    mat = material.upper()
    metals = {"SS", "CARBON", "CAST", "ALLOY", "HASTELLOY", "INCONEL", "BRASS", "MONEL", "TITANIUM", "DUPLEX"}
    elastomers = {"PTFE", "VITON", "EPDM", "NBR", "FKM", "FFKM", "SILICONE", "NEOPRENE", "BUNA"}
    plastics = {"PVC", "CPVC", "PP", "PVDF", "PE", "PEEK", "NYLON", "TEFLON"}
    for token in metals:
        if token in mat:
            return "metal"
    for token in elastomers:
        if token in mat:
            return "elastomer"
    for token in plastics:
        if token in mat:
            return "plastic"
    return "other"


def load_csv(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def parse_row(row: dict) -> dict:
    return {
        "mat_a": row["material_a"].strip(),
        "mat_b": row["material_b"].strip(),
        "cat_a": _infer_category(row["material_a"].strip()),
        "cat_b": _infer_category(row["material_b"].strip()),
        "standard": row["standard"].strip(),
        "pressure": float(row["pressure_bar"]),
        "temp": row["temperature_range"].strip(),
        "confidence": float(row["confidence"]),
    }


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_dry(rows: list[dict]) -> None:
    materials: set[str] = set()
    standards: set[str] = set()
    for row in rows:
        materials.add(row["mat_a"])
        materials.add(row["mat_b"])
        standards.add(row["standard"])
    log.info("DRY-RUN — CSV rows: %d", len(rows))
    log.info("DRY-RUN — Materiales únicos: %d", len(materials))
    log.info("DRY-RUN — Normas únicas: %d", len(standards))
    log.info("DRY-RUN — Ningún dato escrito en Neo4j")


def run_seed(rows: list[dict]) -> None:
    from neo4j import GraphDatabase  # noqa: PLC0415

    log.info("Conectando a Neo4j: %s (db=%s)", NEO4J_URI, NEO4J_DATABASE)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        log.info("Conexión OK")

        with driver.session(database=NEO4J_DATABASE) as session:
            # Constraints
            for cypher in CONSTRAINTS:
                session.run(cypher).consume()
            log.info("Constraints aplicados (%d)", len(CONSTRAINTS))

            # Upsert rows
            merged = 0
            for row in rows:
                params = parse_row(row)
                session.run(MERGE_COMPAT, **params).consume()
                merged += 1

            log.info("Seed completo — %d edges COMPATIBLE_WITH procesados", merged)

    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed KG materiales en Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Parsea CSV y muestra stats sin escribir")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Ruta al CSV de seed (default: scripts/seed_data/kg_materials_seed.csv)")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        log.error("CSV no encontrado: %s", csv_path)
        return 1

    try:
        rows = load_csv(csv_path)
    except Exception as exc:
        log.error("Error leyendo CSV: %s", exc)
        return 1

    log.info("CSV cargado: %d filas desde %s", len(rows), csv_path)

    if args.dry_run:
        run_dry(rows)
        return 0

    try:
        run_seed(rows)
    except Exception as exc:
        log.error("Error en seed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
