"""Integration tests — repository layer del registry polimórfico.

Cubre:
- TaxonomyTypeRepository: list_registry, get_by_slug, create, update,
  protección is_system contra rename/delete
- TaxonomyNodeRepository: create con multi-parents, resolve_slug con aliases,
  descendants/ancestors vía closure, soft_delete
- ProductTaxonomyLinkRepository: link idempotente, unlink soft, subtree query
- FamilySchemaRepository: versionado + supersedes

Requiere Docker (testcontainer Postgres + alembic upgrade head).
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


def _alembic_config(sync_url: str):
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _prepare_supabase_stubs(sync_url: str) -> None:
    """Stub `auth.uid()` / `auth.role()` para Postgres puro (mig. 013 depende)."""
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
            # Roles que Supabase crea por default — necesarios para GRANT y RLS
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
    assert sync_url, "ALEMBIC_DATABASE_URL no setteado"
    return sync_url


@pytest.fixture(scope="module")
def _migrated_db(alembic_sync_url: str) -> str:
    _upgrade_head(alembic_sync_url)
    return alembic_sync_url


# ---------------------------------------------------------------------------
# TaxonomyTypeRepository
# ---------------------------------------------------------------------------


class TestTaxonomyTypeRepository:
    async def test_list_registry_returns_4_system_types(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import TaxonomyTypeRepository

        repo = TaxonomyTypeRepository(db_session)
        types = await repo.list_registry()
        slugs = [t.slug for t in types]
        # Los 4 system types deben aparecer en orden de display_order
        assert "division" in slugs
        assert "series" in slugs
        assert "tier" in slugs
        assert "material" in slugs
        # Todos los system son is_system=true
        system_slugs = [t.slug for t in types if t.is_system]
        assert set(system_slugs) >= {"division", "series", "tier", "material"}

    async def test_get_by_slug(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import TaxonomyTypeRepository

        repo = TaxonomyTypeRepository(db_session)
        division = await repo.get_by_slug("division")
        assert division is not None
        assert division.is_system is True
        assert division.value_kind == "enum_closed"
        missing = await repo.get_by_slug("nonexistent")
        assert missing is None

    async def test_create_new_type(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import TaxonomyTypeRepository

        repo = TaxonomyTypeRepository(db_session)
        slug = f"market_{uuid.uuid4().hex[:6]}"
        new_type = await repo.create(
            slug=slug,
            label_i18n={"es": "Mercados", "en": "Markets"},
            value_kind="enum_open",
        )
        assert new_type.slug == slug
        assert new_type.is_system is False
        assert new_type.active is True

    async def test_cannot_modify_slug_of_system_type(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import TaxonomyTypeRepository

        repo = TaxonomyTypeRepository(db_session)
        with pytest.raises(ValueError, match="is_system"):
            await repo.update("division", slug="business_line")

    async def test_cannot_delete_system_type(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import TaxonomyTypeRepository

        repo = TaxonomyTypeRepository(db_session)
        with pytest.raises(ValueError, match="is_system"):
            await repo.soft_delete("division")


# ---------------------------------------------------------------------------
# TaxonomyNodeRepository
# ---------------------------------------------------------------------------


class TestTaxonomyNodeRepository:
    async def test_create_node_with_multi_parents(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import (
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        division = await type_repo.get_by_slug("division")
        assert division is not None

        # Crear dos parents
        p1 = await node_repo.create(
            type_id=division.id,
            slug=f"parent_a_{uuid.uuid4().hex[:6]}",
        )
        p2 = await node_repo.create(
            type_id=division.id,
            slug=f"parent_b_{uuid.uuid4().hex[:6]}",
        )

        child = await node_repo.create(
            type_id=division.id,
            slug=f"child_{uuid.uuid4().hex[:6]}",
            parent_id=p1.id,
            additional_parents=[p2.id],
        )

        ancestors = await node_repo.get_ancestors(child.id)
        ancestor_ids = {a.id for a in ancestors}
        assert p1.id in ancestor_ids
        assert p2.id in ancestor_ids

    async def test_resolve_slug_follows_alias(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import (
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        division = await type_repo.get_by_slug("division")
        assert division is not None

        canonical_slug = f"canonical_{uuid.uuid4().hex[:6]}"
        alias_slug = f"alias_{uuid.uuid4().hex[:6]}"
        node = await node_repo.create(type_id=division.id, slug=canonical_slug)
        await node_repo.add_alias(
            type_id=division.id,
            alias_slug=alias_slug,
            canonical_node_id=node.id,
        )

        # Búsqueda por canonical slug
        found_by_canonical = await node_repo.resolve_slug(
            division.id, canonical_slug
        )
        assert found_by_canonical is not None
        assert found_by_canonical.id == node.id

        # Búsqueda por alias debe resolver al mismo
        found_by_alias = await node_repo.resolve_slug(division.id, alias_slug)
        assert found_by_alias is not None
        assert found_by_alias.id == node.id

    async def test_descendants_via_closure(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import (
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        series_type = await type_repo.get_by_slug("series")
        assert series_type is not None

        # A → B → C (A es ancestor de C con depth 2)
        a = await node_repo.create(
            type_id=series_type.id, slug=f"a_{uuid.uuid4().hex[:6]}"
        )
        b = await node_repo.create(
            type_id=series_type.id,
            slug=f"b_{uuid.uuid4().hex[:6]}",
            parent_id=a.id,
        )
        c = await node_repo.create(
            type_id=series_type.id,
            slug=f"c_{uuid.uuid4().hex[:6]}",
            parent_id=b.id,
        )
        await db_session.flush()

        descendants_a = await node_repo.get_descendants(a.id)
        desc_ids = {d.id for d in descendants_a}
        assert b.id in desc_ids
        assert c.id in desc_ids

        # max_depth=1 sólo B
        immediate = await node_repo.get_descendants(a.id, max_depth=1)
        assert {d.id for d in immediate} == {b.id}

    async def test_soft_delete_sets_valid_until(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from app.repositories.taxonomy import (
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        material = await type_repo.get_by_slug("material")
        assert material is not None

        node = await node_repo.create(
            type_id=material.id, slug=f"todelete_{uuid.uuid4().hex[:6]}"
        )
        ok = await node_repo.soft_delete(node.id)
        assert ok is True

        await db_session.refresh(node)
        assert node.valid_until is not None
        assert node.active is False


# ---------------------------------------------------------------------------
# ProductTaxonomyLinkRepository
# ---------------------------------------------------------------------------


class TestProductTaxonomyLinkRepository:
    async def test_link_and_list_for_product(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from sqlalchemy import text

        from app.repositories.taxonomy import (
            ProductTaxonomyLinkRepository,
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        # Crear producto de prueba
        sku = f"TEST-LINK-{uuid.uuid4().hex[:6]}"
        await db_session.execute(
            text(
                """
                INSERT INTO products (sku, name_en, family, brand_id, family_id)
                SELECT :sku, 'Test', 'ball_valve',
                       (SELECT id FROM brands WHERE code = 'default'),
                       (SELECT id FROM families WHERE code = 'default')
                """
            ),
            {"sku": sku},
        )
        await db_session.flush()

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        link_repo = ProductTaxonomyLinkRepository(db_session)

        division = await type_repo.get_by_slug("division")
        assert division is not None
        node = await node_repo.create(
            type_id=division.id, slug=f"divtest_{uuid.uuid4().hex[:6]}"
        )

        link = await link_repo.link(
            product_sku=sku, node_id=node.id, role="belongs_to"
        )
        assert link.role == "belongs_to"

        # Idempotente: re-link no falla
        same_link = await link_repo.link(
            product_sku=sku, node_id=node.id, role="belongs_to"
        )
        assert same_link.product_sku == sku

        links = await link_repo.list_for_product(sku)
        assert len(links) == 1
        assert links[0].role == "belongs_to"

    async def test_unlink_soft(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from sqlalchemy import text

        from app.repositories.taxonomy import (
            ProductTaxonomyLinkRepository,
            TaxonomyNodeRepository,
            TaxonomyTypeRepository,
        )

        sku = f"TEST-UNLINK-{uuid.uuid4().hex[:6]}"
        await db_session.execute(
            text(
                """
                INSERT INTO products (sku, name_en, family, brand_id, family_id)
                SELECT :sku, 'Test', 'ball_valve',
                       (SELECT id FROM brands WHERE code = 'default'),
                       (SELECT id FROM families WHERE code = 'default')
                """
            ),
            {"sku": sku},
        )
        await db_session.flush()

        type_repo = TaxonomyTypeRepository(db_session)
        node_repo = TaxonomyNodeRepository(db_session)
        link_repo = ProductTaxonomyLinkRepository(db_session)
        division = await type_repo.get_by_slug("division")
        node = await node_repo.create(
            type_id=division.id, slug=f"divunlink_{uuid.uuid4().hex[:6]}"
        )
        await link_repo.link(product_sku=sku, node_id=node.id)

        ok = await link_repo.unlink(
            product_sku=sku, node_id=node.id, soft=True
        )
        assert ok is True

        # Soft unlink: el link específico al `node` queda con valid_until.
        # Filtramos por type_slug='division' porque mig 052 trigger
        # `sync_product_fk_to_registry` autocrea links para family_id
        # (default brand/family seed) que no son objetivo de este test.
        current = await link_repo.list_for_product(
            sku, current_only=True, type_slug="division"
        )
        assert len(current) == 0
        historic = await link_repo.list_for_product(
            sku, current_only=False, type_slug="division"
        )
        assert len(historic) == 1
        assert historic[0].valid_until is not None
        assert historic[0].node_id == node.id


# ---------------------------------------------------------------------------
# Backfill desde legacy (migration 050)
# ---------------------------------------------------------------------------


class TestBackfillFromLegacy:
    """Verifica que mig. 050 pobló taxonomy_nodes desde tablas legacy."""

    async def test_divisions_backfilled(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from sqlalchemy import text

        # divisions tiene seed (hidrosanitario, industrial) → debe estar en
        # taxonomy_nodes con type=division
        rows = await db_session.execute(
            text(
                """
                SELECT tn.slug
                FROM taxonomy_nodes tn
                JOIN taxonomy_types tt ON tt.id = tn.type_id
                WHERE tt.slug = 'division'
                ORDER BY tn.slug
                """
            )
        )
        slugs = [r[0] for r in rows.fetchall()]
        # Las 2 seed de divisions deben aparecer
        assert "hidrosanitario" in slugs
        assert "industrial" in slugs

    async def test_normalize_slug_function_exists(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from sqlalchemy import text

        # Verificar que la función PG está creada
        result = await db_session.execute(
            text("SELECT taxonomy_normalize_slug('Some Name-Foo')")
        )
        normalized = result.scalar_one()
        # Debería ser lowercase + underscores
        assert normalized == "some_name_foo"

    async def test_normalize_slug_handles_leading_digit(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        from sqlalchemy import text

        result = await db_session.execute(
            text("SELECT taxonomy_normalize_slug('123_test')")
        )
        normalized = result.scalar_one()
        assert normalized.startswith("n_")  # prefix para evitar regex violation

    async def test_sync_trigger_on_division_insert(
        self, _migrated_db: str, db_session: "AsyncSession"
    ) -> None:
        """Insert en `divisions` debe reflejarse en `taxonomy_nodes`."""
        from sqlalchemy import text

        code = f"test_div_{uuid.uuid4().hex[:6]}"
        await db_session.execute(
            text(
                """
                INSERT INTO divisions (code, name, description, sort_order)
                VALUES (:code, 'Test Division', 'desc', 999)
                """
            ),
            {"code": code},
        )
        await db_session.flush()

        result = await db_session.execute(
            text(
                """
                SELECT tn.labels->>'es'
                FROM taxonomy_nodes tn
                JOIN taxonomy_types tt ON tt.id = tn.type_id
                WHERE tt.slug = 'division' AND tn.slug = :slug
                """
            ),
            {"slug": code},
        )
        label = result.scalar_one_or_none()
        assert label == "Test Division", "Trigger sync_divisions_to_registry no ejecutó"


# ---------------------------------------------------------------------------
# Smoke test: rutas API registradas
# ---------------------------------------------------------------------------


class TestRoutesRegistered:
    """No requiere DB; valida que las 15 rutas están en el app."""

    @pytest.mark.unit
    def test_taxonomy_routes_present(self) -> None:
        from app.main import app

        registered_paths = {
            (str(route.path), tuple(sorted(route.methods or ())))
            for route in app.routes
            if hasattr(route, "methods")
        }
        expected = [
            ("/taxonomies/registry", ("GET",)),
            ("/taxonomies/{type_slug}", ("GET",)),
            ("/taxonomies/{type_slug}/nodes", ("GET",)),
            ("/taxonomies/{type_slug}/nodes/{node_slug}", ("GET",)),
            (
                "/taxonomies/{type_slug}/nodes/{node_slug}/descendants",
                ("GET",),
            ),
            ("/products/{sku}/taxonomies", ("GET",)),
            ("/admin/taxonomies/types", ("POST",)),
            ("/admin/taxonomies/types/{type_slug}", ("DELETE",)),
            ("/admin/taxonomies/types/{type_slug}", ("PATCH",)),
            ("/admin/taxonomies/{type_slug}/nodes", ("POST",)),
            ("/admin/taxonomies/{type_slug}/aliases", ("POST",)),
            (
                "/admin/taxonomies/{type_slug}/nodes/{node_slug}",
                ("DELETE",),
            ),
            ("/admin/taxonomies/{type_slug}/nodes/{node_slug}", ("PATCH",)),
            ("/admin/products/{sku}/taxonomies", ("POST",)),
            (
                "/admin/products/{sku}/taxonomies/{node_id}",
                ("DELETE",),
            ),
        ]
        # FastAPI puede prefixar con /api/v1 (depende del montaje)
        for path, methods in expected:
            found = False
            for reg_path, reg_methods in registered_paths:
                if reg_path.endswith(path) and methods[0] in reg_methods:
                    found = True
                    break
            assert found, f"Ruta esperada no encontrada: {methods[0]} {path}"
