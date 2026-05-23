"""Fixtures de integración compartidas.

`neo4j_driver` (session-scoped) — driver sincrónico apuntando al Neo4j
local de desarrollo (bolt://localhost:17687 por defecto).

Usado por tests marcados con @pytest.mark.neo4j_real.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def neo4j_driver():
    """Driver Neo4j sincrónico apuntando a la instancia local de dev.

    Lee credenciales de variables de entorno con fallback a defaults dev.
    """
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:17687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "devpassword")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()
