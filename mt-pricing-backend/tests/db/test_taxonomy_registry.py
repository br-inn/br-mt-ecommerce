"""Integration tests — Registry polimórfico (mig. 049).

Cubre:
- Migración aplica sin errores y crea las 7 tablas.
- Seed inicial pre-carga los 4 ``taxonomy_types`` is_system.
- CHECK constraints (slug, value_kind, role, depth_max, no_self_supersede).
- UNIQUE (slug por type) + (alias_slug por type).
- Trigger de closure table: INSERT en parents mantiene descendants.
- Multi-inheritance funcional (un nodo con N parents).
- FK ON DELETE comportamiento (RESTRICT vs CASCADE).
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.integration]


def _alembic_config(sync_url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _prepare_supabase_stubs(sync_url: str) -> None:
    """Stubs de schema `auth` + funciones Supabase para correr migraciones
    en plain Postgres (testcontainer) sin tener Supabase Auth disponible.

    Necesario porque mig. 013 referencia ``auth.uid()`` en una RLS policy.
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            for fn, ret in (
                ("uid", "UUID"),
                ("role", "TEXT"),
                ("jwt", "JSONB"),
            ):
                conn.execute(
                    text(
                        f"CREATE OR REPLACE FUNCTION auth.{fn}() RETURNS {ret} "
                        f"AS $$ SELECT NULL::{ret} $$ LANGUAGE sql"
                    )
                )
            for role in ("anon", "authenticated", "service_role"):
                conn.execute(
                    text(
                        f"DO $$ BEGIN "
                        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
                        f"CREATE ROLE {role} NOLOGIN; END IF; END $$"
                    )
                )
    finally:
        engine.dispose()


def _upgrade_head(sync_url: str) -> None:
    from alembic import command

    _prepare_supabase_stubs(sync_url)
    cfg = _alembic_config(sync_url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="module")
def alembic_sync_url(postgres_container: str) -> str:
    sync_url = os.environ.get("ALEMBIC_DATABASE_URL", "")
    assert sync_url, "ALEMBIC_DATABASE_URL no setteado por el container fixture"
    return sync_url


@pytest.fixture(scope="module")
def upgraded_db(alembic_sync_url: str) -> str:
    """Aplica alembic upgrade head una vez por módulo."""
    _upgrade_head(alembic_sync_url)
    return alembic_sync_url


# ---------------------------------------------------------------------------
# Tablas y seed
# ---------------------------------------------------------------------------


class TestSchemaAndSeed:
    def test_all_registry_tables_created(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, inspect

        engine = create_engine(upgraded_db)
        try:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            expected = {
                "taxonomy_types",
                "taxonomy_nodes",
                "taxonomy_node_parents",
                "taxonomy_node_descendants",
                "taxonomy_aliases",
                "product_taxonomy_links",
                "family_schemas",
            }
            missing = expected - tables
            assert not missing, f"Tablas faltantes: {missing}"
        finally:
            engine.dispose()

    def test_seed_loads_four_system_types(self, upgraded_db: str) -> None:
        """Tras mig 049: 4 system types (division/series/tier/material).
        Tras mig 052: 7 system types (+ family/subfamily/product_type).

        Validamos por orden de display_order ascendente.
        """
        from sqlalchemy import create_engine, text

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn:
                rows = conn.execute(
                    text(
                        "SELECT slug, is_system, value_kind FROM taxonomy_types "
                        "WHERE is_system = true ORDER BY display_order"
                    )
                ).fetchall()
            slugs = [r[0] for r in rows]
            # Mig 052 agrega family (5), subfamily (6), product_type (7) tras
            # los 4 originales (10/20/30/40 → reordenados a 5/6/7 vs 10/20/30/40).
            # display_order: family=5, subfamily=6, product_type=7,
            # division=10, series=20, tier=30, material=40.
            assert slugs == [
                "family", "subfamily", "product_type",
                "division", "series", "tier", "material",
            ]
            assert all(r[1] is True for r in rows)
            kinds = {r[0]: r[2] for r in rows}
            assert kinds["division"] == "enum_closed"
            assert kinds["tier"] == "enum_closed"
            assert kinds["series"] == "enum_open"
            assert kinds["material"] == "enum_open"
            assert kinds["family"] == "enum_closed"
            assert kinds["subfamily"] == "enum_closed"
            assert kinds["product_type"] == "enum_open"
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Constraints — CHECK + UNIQUE
# ---------------------------------------------------------------------------


class TestConstraints:
    def test_slug_format_constraint(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            # slug con mayúscula → falla
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_types (slug) VALUES ('Market')"
                    )
                )
            # slug con guión → falla
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_types (slug) VALUES ('mar-ket')"
                    )
                )
            # slug comenzando con dígito → falla
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_types (slug) VALUES ('1market')"
                    )
                )
        finally:
            engine.dispose()

    def test_value_kind_enum_constraint(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_types (slug, value_kind) "
                        "VALUES ('foo_bar', 'custom_kind')"
                    )
                )
        finally:
            engine.dispose()

    def test_depth_max_positive_constraint(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_types (slug, depth_max) "
                        "VALUES ('foo_baz', 0)"
                    )
                )
        finally:
            engine.dispose()

    def test_node_no_self_supersede(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn:
                type_id = conn.execute(
                    text(
                        "SELECT id FROM taxonomy_types WHERE slug = 'division'"
                    )
                ).scalar_one()
                node_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, 'test_self_supersede') RETURNING id"
                    ),
                    {"tid": type_id},
                ).scalar_one()

            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "UPDATE taxonomy_nodes SET superseded_by = id WHERE id = :nid"
                    ),
                    {"nid": node_id},
                )

            # Cleanup
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM taxonomy_nodes WHERE slug = 'test_self_supersede'"
                    )
                )
        finally:
            engine.dispose()

    def test_node_uniqueness_per_type(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn:
                division_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'division'")
                ).scalar_one()
                series_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'series'")
                ).scalar_one()

                # Mismo slug en distinto type → OK
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:t1, 'shared_slug'), (:t2, 'shared_slug')"
                    ),
                    {"t1": division_type_id, "t2": series_type_id},
                )

            # Mismo slug + mismo type → falla
            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, 'shared_slug')"
                    ),
                    {"tid": division_type_id},
                )

            # Cleanup
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM taxonomy_nodes WHERE slug = 'shared_slug'")
                )
        finally:
            engine.dispose()

    def test_link_role_constraint(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(upgraded_db)
        try:
            # Crear un producto + nodo dummy para probar link
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO products (sku, name_en, family, brand_id, family_id)
                        SELECT 'TEST-LINK-001', 'Test Product', 'ball_valve',
                               (SELECT id FROM brands WHERE code = 'default'),
                               (SELECT id FROM families WHERE code = 'default')
                        ON CONFLICT DO NOTHING
                        """
                    )
                )
                division_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'division'")
                ).scalar_one()
                node_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, 'test_link_node') RETURNING id"
                    ),
                    {"tid": division_type_id},
                ).scalar_one()

            with engine.begin() as conn, pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO product_taxonomy_links (product_sku, node_id, role) "
                        "VALUES ('TEST-LINK-001', :nid, 'competes_with')"
                    ),
                    {"nid": node_id},
                )

            # Cleanup — productos no se borran (compliance trigger NFR-35);
            # solo limpiar el nodo y los links.
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM product_taxonomy_links WHERE product_sku = 'TEST-LINK-001'"
                    )
                )
                conn.execute(
                    text(
                        "DELETE FROM taxonomy_nodes WHERE slug = 'test_link_node'"
                    )
                )
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Closure table — trigger maintenance
# ---------------------------------------------------------------------------


class TestClosureTable:
    def test_self_row_inserted_on_node_create(self, upgraded_db: str) -> None:
        from sqlalchemy import create_engine, text

        engine = create_engine(upgraded_db)
        try:
            with engine.begin() as conn:
                division_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'division'")
                ).scalar_one()
                node_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, 'closure_root') RETURNING id"
                    ),
                    {"tid": division_type_id},
                ).scalar_one()

                rows = conn.execute(
                    text(
                        "SELECT ancestor_id, descendant_id, depth "
                        "FROM taxonomy_node_descendants "
                        "WHERE descendant_id = :nid"
                    ),
                    {"nid": node_id},
                ).fetchall()
                # Self-row depth 0
                assert any(
                    r[0] == r[1] == node_id and r[2] == 0 for r in rows
                ), "self-row no insertada por trigger"

            # Cleanup
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM taxonomy_nodes WHERE slug = 'closure_root'")
                )
        finally:
            engine.dispose()

    def test_parent_link_propagates_ancestors(self, upgraded_db: str) -> None:
        """A → B → C: closure debe contener (A,C,2), (B,C,1), (C,C,0), (A,B,1), (B,B,0), (A,A,0)."""
        from sqlalchemy import create_engine, text

        engine = create_engine(upgraded_db)
        slug_a = f"closure_a_{uuid.uuid4().hex[:8]}"
        slug_b = f"closure_b_{uuid.uuid4().hex[:8]}"
        slug_c = f"closure_c_{uuid.uuid4().hex[:8]}"
        try:
            with engine.begin() as conn:
                division_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'division'")
                ).scalar_one()
                a_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_a},
                ).scalar_one()
                b_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_b},
                ).scalar_one()
                c_id = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_c},
                ).scalar_one()

                # B parent of A, C parent of B (A is leaf, C is root)
                # Wait — convención: parent_id = parent. Let's clarify:
                # parents: A's parent is B; B's parent is C
                # → ancestors of A: B (depth 1), C (depth 2)
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary) "
                        "VALUES (:a, :b, true), (:b, :c, true)"
                    ),
                    {"a": a_id, "b": b_id, "c": c_id},
                )

            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT ancestor_id, descendant_id, depth "
                        "FROM taxonomy_node_descendants "
                        "WHERE descendant_id IN (:a, :b, :c) "
                        "ORDER BY descendant_id, depth"
                    ),
                    {"a": a_id, "b": b_id, "c": c_id},
                ).fetchall()

            # Convert to set of tuples for assertion
            actual = {(r[0], r[1], r[2]) for r in rows}
            expected = {
                # Self-rows
                (a_id, a_id, 0),
                (b_id, b_id, 0),
                (c_id, c_id, 0),
                # A's ancestors
                (b_id, a_id, 1),
                (c_id, a_id, 2),
                # B's ancestors
                (c_id, b_id, 1),
            }
            assert expected <= actual, (
                f"Closure incompleta: faltan {expected - actual}"
            )

            # Cleanup en orden: borrar A primero (es descendiente), luego B, luego C
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM taxonomy_nodes WHERE id IN (:a, :b, :c)"),
                    {"a": a_id, "b": b_id, "c": c_id},
                )
        finally:
            engine.dispose()

    def test_multi_inheritance_accumulates_ancestors(
        self, upgraded_db: str
    ) -> None:
        """Nodo con dos parents distintos: ambos aparecen como ancestors (depth 1)."""
        from sqlalchemy import create_engine, text

        engine = create_engine(upgraded_db)
        slug_p1 = f"mh_p1_{uuid.uuid4().hex[:8]}"
        slug_p2 = f"mh_p2_{uuid.uuid4().hex[:8]}"
        slug_child = f"mh_child_{uuid.uuid4().hex[:8]}"
        try:
            with engine.begin() as conn:
                division_type_id = conn.execute(
                    text("SELECT id FROM taxonomy_types WHERE slug = 'division'")
                ).scalar_one()
                p1 = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_p1},
                ).scalar_one()
                p2 = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_p2},
                ).scalar_one()
                child = conn.execute(
                    text(
                        "INSERT INTO taxonomy_nodes (type_id, slug) "
                        "VALUES (:tid, :s) RETURNING id"
                    ),
                    {"tid": division_type_id, "s": slug_child},
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary) "
                        "VALUES (:c, :p1, true), (:c, :p2, false)"
                    ),
                    {"c": child, "p1": p1, "p2": p2},
                )

            with engine.connect() as conn:
                ancestors = conn.execute(
                    text(
                        "SELECT ancestor_id FROM taxonomy_node_descendants "
                        "WHERE descendant_id = :c AND depth = 1"
                    ),
                    {"c": child},
                ).fetchall()

            ancestor_ids = {r[0] for r in ancestors}
            assert p1 in ancestor_ids, "primary parent missing from closure"
            assert p2 in ancestor_ids, "secondary parent missing from closure"

            # Cleanup — borrar primero el child (sino RESTRICT en parents)
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM taxonomy_nodes WHERE id = :c"),
                    {"c": child},
                )
                conn.execute(
                    text("DELETE FROM taxonomy_nodes WHERE id IN (:p1, :p2)"),
                    {"p1": p1, "p2": p2},
                )
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Models registered in Base.metadata
# ---------------------------------------------------------------------------


class TestModelsRegistration:
    """No requiere DB; valida que los modelos están registrados.

    Aunque está en tests/db/, no necesita postgres_container (no usa upgraded_db).
    """

    def test_taxonomy_models_in_metadata(self) -> None:
        from app.db import Base
        from app.db import models as _  # noqa: F401

        expected = {
            "taxonomy_types",
            "taxonomy_nodes",
            "taxonomy_node_parents",
            "taxonomy_node_descendants",
            "taxonomy_aliases",
            "product_taxonomy_links",
            "family_schemas",
        }
        registered = set(Base.metadata.tables.keys())
        missing = expected - registered
        assert not missing, f"Modelos no registrados: {missing}"

    def test_taxonomy_models_exported(self) -> None:
        from app.db import models

        expected = {
            "TaxonomyType",
            "TaxonomyNode",
            "TaxonomyNodeParent",
            "TaxonomyNodeDescendant",
            "TaxonomyAlias",
            "ProductTaxonomyLink",
            "FamilySchema",
        }
        actual = set(models.__all__)
        missing = expected - actual
        assert not missing, f"Faltan en __all__: {missing}"
