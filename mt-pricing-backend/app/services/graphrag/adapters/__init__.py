"""Graph store adapters — implementaciones concretas de `GraphStorePort`.

Fase 1 (S4): solo el `Neo4jStubGraphStore` (in-memory).
Fase 2+ (ADR-041): añadir `Neo4jGraphStore` (driver real) y/o
`PostgresAgeGraphStore` (Apache AGE) sin tocar el resto del código.
"""

from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

__all__ = ["Neo4jStubGraphStore"]
