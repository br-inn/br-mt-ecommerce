"""family_to_registry — registrar family/subfamily/product_type en taxonomy_registry.

Extiende migración 050 (que ya hace divisions/series/tiers/materials) agregando
los 3 niveles jerárquicos restantes — family, subfamily, product_type — al
registry polimórfico.

Justificación: el filtro "Familia" del catálogo seguía hardcoded contra el
`/taxonomy/tree` legacy. Tras esta migración:

- ``taxonomy_types`` recibe 3 entries nuevas (``is_system=true``):
  - ``family``     (depth_max=1, position 5)
  - ``subfamily``  (depth_max=2, position 6)
  - ``product_type`` (depth_max=3, position 7)

- ``taxonomy_nodes`` se llena con un row por cada fila de las tablas legacy
  ``families``, ``subfamilies``, ``product_types``. parent_id apunta al nodo
  padre del nivel superior cuando aplica (subfamily.family_id → family node).
  El cierre transitivo (taxonomy_node_parents) también se backfillea para
  habilitar queries de descendiente vía closure table.

- ``product_taxonomy_links`` recibe role='belongs_to' para los productos con
  family_id NOT NULL (mig. 048 lo promovió). subfamily_id/type_id se linkean
  cuando no son NULL (siguen nullable).

- Sync triggers one-way (legacy → registry) idénticos en patrón a los de mig
  050. Loop prevention via session var ``app.taxonomy_sync_skip``.

- El trigger existente ``sync_product_fk_to_registry`` (mig 050) se REEMPLAZA
  con una versión que ALSO sincroniza family_id/subfamily_id/type_id, además
  de la lógica existente series_id/material_id.

Revision ID: 20260512_052
Revises: 20260511_051
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260512_052"
down_revision: str | None = "20260511_051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Seed taxonomy_types para family / subfamily / product_type
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_types (
            slug, is_system, label_i18n, is_hierarchical, depth_max, value_kind,
            filterable, display_order, ui_layout, governance_policy,
            required_for_products, external_mappings, active
        ) VALUES
        (
            'family', true,
            '{"es": "Familias", "en": "Families", "ar": "العائلات"}'::jsonb,
            true, 1, 'enum_closed',
            true, 5,
            '{"icon": "tags", "position": 5}'::jsonb,
            '{"approval_required": true, "allowed_creator_roles": ["admin"]}'::jsonb,
            true,
            '{"schema_org": "category"}'::jsonb,
            true
        ),
        (
            'subfamily', true,
            '{"es": "Subfamilias", "en": "Subfamilies", "ar": "العائلات الفرعية"}'::jsonb,
            true, 2, 'enum_closed',
            true, 6,
            '{"icon": "tag", "position": 6}'::jsonb,
            '{"approval_required": true, "allowed_creator_roles": ["admin", "product_manager"]}'::jsonb,
            false,
            '{}'::jsonb,
            true
        ),
        (
            'product_type', true,
            '{"es": "Tipos", "en": "Product Types", "ar": "أنواع المنتجات"}'::jsonb,
            true, 3, 'enum_open',
            true, 7,
            '{"icon": "package", "position": 7}'::jsonb,
            '{"approval_required": false, "allowed_creator_roles": ["admin", "product_manager"]}'::jsonb,
            false,
            '{}'::jsonb,
            true
        )
        ON CONFLICT (slug) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 2. Backfill taxonomy_nodes desde families
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
        SELECT
            tt.id AS type_id,
            taxonomy_normalize_slug(f.code) AS slug,
            jsonb_build_object('es', f.name, 'en', f.name) AS labels,
            f.sort_order AS display_order,
            f.active,
            jsonb_build_object('description', f.description, 'sort_order', f.sort_order)
        FROM families f
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'family'
        ) tt
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 3. Backfill taxonomy_nodes desde subfamilies (parent = family node)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (
            type_id, slug, labels, display_order, active, attributes, parent_id
        )
        SELECT
            tt_sub.id AS type_id,
            taxonomy_normalize_slug(sf.code) AS slug,
            jsonb_build_object('es', sf.name, 'en', sf.name) AS labels,
            sf.sort_order AS display_order,
            sf.active,
            jsonb_build_object('description', sf.description, 'sort_order', sf.sort_order),
            fam_node.id AS parent_id
        FROM subfamilies sf
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'subfamily'
        ) tt_sub
        JOIN families f ON f.id = sf.family_id
        LEFT JOIN LATERAL (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt_f ON tt_f.id = tn.type_id AND tt_f.slug = 'family'
            WHERE tn.slug = taxonomy_normalize_slug(f.code)
            LIMIT 1
        ) fam_node ON true
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # Backfill closure family→subfamily.
    op.execute(
        """
        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
        SELECT sub_node.id, fam_node.id, true
        FROM subfamilies sf
        JOIN families f ON f.id = sf.family_id
        JOIN taxonomy_nodes sub_node ON sub_node.slug = taxonomy_normalize_slug(sf.code)
            AND sub_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'subfamily')
        JOIN taxonomy_nodes fam_node ON fam_node.slug = taxonomy_normalize_slug(f.code)
            AND fam_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'family')
        ON CONFLICT (node_id, parent_id) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 4. Backfill taxonomy_nodes desde product_types (parent = subfamily node)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (
            type_id, slug, labels, display_order, active, attributes, parent_id
        )
        SELECT
            tt_pt.id AS type_id,
            taxonomy_normalize_slug(pt.code) AS slug,
            jsonb_build_object('es', pt.name, 'en', pt.name) AS labels,
            pt.sort_order AS display_order,
            pt.active,
            jsonb_build_object('description', pt.description, 'sort_order', pt.sort_order),
            sub_node.id AS parent_id
        FROM product_types pt
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'product_type'
        ) tt_pt
        JOIN subfamilies sf ON sf.id = pt.subfamily_id
        LEFT JOIN LATERAL (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt_sub ON tt_sub.id = tn.type_id AND tt_sub.slug = 'subfamily'
            WHERE tn.slug = taxonomy_normalize_slug(sf.code)
            LIMIT 1
        ) sub_node ON true
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # Backfill closure subfamily→product_type.
    op.execute(
        """
        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
        SELECT pt_node.id, sub_node.id, true
        FROM product_types pt
        JOIN subfamilies sf ON sf.id = pt.subfamily_id
        JOIN taxonomy_nodes pt_node ON pt_node.slug = taxonomy_normalize_slug(pt.code)
            AND pt_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'product_type')
        JOIN taxonomy_nodes sub_node ON sub_node.slug = taxonomy_normalize_slug(sf.code)
            AND sub_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'subfamily')
        ON CONFLICT (node_id, parent_id) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 5. Backfill product_taxonomy_links desde products.family_id (NOT NULL)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT p.sku, tn.id, 'belongs_to'
        FROM products p
        JOIN families f ON f.id = p.family_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(f.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'family')
        WHERE p.family_id IS NOT NULL
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT p.sku, tn.id, 'belongs_to'
        FROM products p
        JOIN subfamilies sf ON sf.id = p.subfamily_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(sf.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'subfamily')
        WHERE p.subfamily_id IS NOT NULL
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT p.sku, tn.id, 'belongs_to'
        FROM products p
        JOIN product_types pt ON pt.id = p.type_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(pt.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'product_type')
        WHERE p.type_id IS NOT NULL
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 6. Sync trigger: families → taxonomy_nodes(type='family')
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_families_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            old_slug TEXT;
            new_slug TEXT;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'family';

            IF TG_OP = 'INSERT' THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.sort_order,
                    NEW.active,
                    jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order)
                )
                ON CONFLICT (type_id, slug) DO UPDATE
                SET labels = EXCLUDED.labels,
                    display_order = EXCLUDED.display_order,
                    active = EXCLUDED.active,
                    attributes = EXCLUDED.attributes;

            ELSIF TG_OP = 'UPDATE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                new_slug := taxonomy_normalize_slug(NEW.code);
                UPDATE taxonomy_nodes
                SET slug = new_slug,
                    labels = jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    display_order = NEW.sort_order,
                    active = NEW.active,
                    attributes = jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order)
                WHERE type_id = type_id_var AND slug = old_slug;

            ELSIF TG_OP = 'DELETE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET valid_until = now(), active = false
                WHERE type_id = type_id_var AND slug = old_slug;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_families_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON families
        FOR EACH ROW EXECUTE FUNCTION sync_families_to_registry();
        """
    )

    # ------------------------------------------------------------------
    # 7. Sync trigger: subfamilies → taxonomy_nodes(type='subfamily') + parent
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_subfamilies_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            family_type_id UUID;
            old_slug TEXT;
            new_slug TEXT;
            node_id_var UUID;
            family_node_id UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'subfamily';
            SELECT id INTO family_type_id FROM taxonomy_types WHERE slug = 'family';

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                family_node_id := NULL;
                IF NEW.family_id IS NOT NULL THEN
                    SELECT tn.id INTO family_node_id
                    FROM taxonomy_nodes tn
                    JOIN families f ON taxonomy_normalize_slug(f.code) = tn.slug
                    WHERE f.id = NEW.family_id AND tn.type_id = family_type_id;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO taxonomy_nodes (
                    type_id, slug, labels, display_order, active, attributes, parent_id
                )
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.sort_order,
                    NEW.active,
                    jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order),
                    family_node_id
                )
                ON CONFLICT (type_id, slug) DO UPDATE
                SET labels = EXCLUDED.labels,
                    display_order = EXCLUDED.display_order,
                    active = EXCLUDED.active,
                    attributes = EXCLUDED.attributes,
                    parent_id = EXCLUDED.parent_id
                RETURNING id INTO node_id_var;

                IF family_node_id IS NOT NULL AND node_id_var IS NOT NULL THEN
                    INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                    VALUES (node_id_var, family_node_id, true)
                    ON CONFLICT (node_id, parent_id) DO UPDATE SET is_primary = true;
                END IF;

            ELSIF TG_OP = 'UPDATE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET slug = new_slug,
                    labels = jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    display_order = NEW.sort_order,
                    active = NEW.active,
                    attributes = jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order),
                    parent_id = family_node_id
                WHERE type_id = type_id_var AND slug = old_slug
                RETURNING id INTO node_id_var;

                IF node_id_var IS NOT NULL THEN
                    DELETE FROM taxonomy_node_parents
                    WHERE node_id = node_id_var AND is_primary = true;
                    IF family_node_id IS NOT NULL THEN
                        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                        VALUES (node_id_var, family_node_id, true)
                        ON CONFLICT (node_id, parent_id) DO UPDATE SET is_primary = true;
                    END IF;
                END IF;

            ELSIF TG_OP = 'DELETE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET valid_until = now(), active = false
                WHERE type_id = type_id_var AND slug = old_slug;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_subfamilies_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON subfamilies
        FOR EACH ROW EXECUTE FUNCTION sync_subfamilies_to_registry();
        """
    )

    # ------------------------------------------------------------------
    # 8. Sync trigger: product_types → taxonomy_nodes(type='product_type') + parent
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_product_types_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            subfamily_type_id UUID;
            old_slug TEXT;
            new_slug TEXT;
            node_id_var UUID;
            subfamily_node_id UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'product_type';
            SELECT id INTO subfamily_type_id FROM taxonomy_types WHERE slug = 'subfamily';

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                subfamily_node_id := NULL;
                IF NEW.subfamily_id IS NOT NULL THEN
                    SELECT tn.id INTO subfamily_node_id
                    FROM taxonomy_nodes tn
                    JOIN subfamilies sf ON taxonomy_normalize_slug(sf.code) = tn.slug
                    WHERE sf.id = NEW.subfamily_id AND tn.type_id = subfamily_type_id;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO taxonomy_nodes (
                    type_id, slug, labels, display_order, active, attributes, parent_id
                )
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.sort_order,
                    NEW.active,
                    jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order),
                    subfamily_node_id
                )
                ON CONFLICT (type_id, slug) DO UPDATE
                SET labels = EXCLUDED.labels,
                    display_order = EXCLUDED.display_order,
                    active = EXCLUDED.active,
                    attributes = EXCLUDED.attributes,
                    parent_id = EXCLUDED.parent_id
                RETURNING id INTO node_id_var;

                IF subfamily_node_id IS NOT NULL AND node_id_var IS NOT NULL THEN
                    INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                    VALUES (node_id_var, subfamily_node_id, true)
                    ON CONFLICT (node_id, parent_id) DO UPDATE SET is_primary = true;
                END IF;

            ELSIF TG_OP = 'UPDATE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET slug = new_slug,
                    labels = jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    display_order = NEW.sort_order,
                    active = NEW.active,
                    attributes = jsonb_build_object('description', NEW.description, 'sort_order', NEW.sort_order),
                    parent_id = subfamily_node_id
                WHERE type_id = type_id_var AND slug = old_slug
                RETURNING id INTO node_id_var;

                IF node_id_var IS NOT NULL THEN
                    DELETE FROM taxonomy_node_parents
                    WHERE node_id = node_id_var AND is_primary = true;
                    IF subfamily_node_id IS NOT NULL THEN
                        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                        VALUES (node_id_var, subfamily_node_id, true)
                        ON CONFLICT (node_id, parent_id) DO UPDATE SET is_primary = true;
                    END IF;
                END IF;

            ELSIF TG_OP = 'DELETE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET valid_until = now(), active = false
                WHERE type_id = type_id_var AND slug = old_slug;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_product_types_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON product_types
        FOR EACH ROW EXECUTE FUNCTION sync_product_types_to_registry();
        """
    )

    # ------------------------------------------------------------------
    # 9. REEMPLAZAR sync_product_fk_to_registry para incluir family/subfamily/type
    # ------------------------------------------------------------------
    # Re-creamos la función (los triggers usan FUNCTION por nombre, así que
    # CREATE OR REPLACE basta). Mantenemos lógica existente series/material.
    # También extendemos el TRIGGER para escuchar cambios en family_id,
    # subfamily_id y type_id (DROP + re-CREATE necesario para alterar columnas
    # de UPDATE OF).
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_sync_product_fk_to_registry ON products;

        CREATE OR REPLACE FUNCTION sync_product_fk_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            old_series_node UUID;
            new_series_node UUID;
            old_material_node UUID;
            new_material_node UUID;
            old_family_node UUID;
            new_family_node UUID;
            old_subfamily_node UUID;
            new_subfamily_node UUID;
            old_type_node UUID;
            new_type_node UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            -- ============= SERIES sync (lógica preservada de mig 050) =============
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.series_id IS DISTINCT FROM NEW.series_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.series_id IS NOT NULL THEN
                    SELECT tn.id INTO old_series_node
                    FROM series s
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(s.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
                    WHERE s.id = OLD.series_id;
                    IF old_series_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_series_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.series_id IS NOT NULL THEN
                    SELECT tn.id INTO new_series_node
                    FROM series s
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(s.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
                    WHERE s.id = NEW.series_id;
                    IF new_series_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_series_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            -- ============= MATERIAL sync (lógica preservada de mig 050) ============
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.material_id IS DISTINCT FROM NEW.material_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.material_id IS NOT NULL THEN
                    SELECT tn.id INTO old_material_node
                    FROM materials m
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(m.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'material')
                    WHERE m.id = OLD.material_id;
                    IF old_material_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_material_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.material_id IS NOT NULL THEN
                    SELECT tn.id INTO new_material_node
                    FROM materials m
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(m.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'material')
                    WHERE m.id = NEW.material_id;
                    IF new_material_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_material_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            -- ============= FAMILY sync (NEW en mig 052) =============
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.family_id IS DISTINCT FROM NEW.family_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.family_id IS NOT NULL THEN
                    SELECT tn.id INTO old_family_node
                    FROM families f
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(f.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'family')
                    WHERE f.id = OLD.family_id;
                    IF old_family_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_family_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.family_id IS NOT NULL THEN
                    SELECT tn.id INTO new_family_node
                    FROM families f
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(f.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'family')
                    WHERE f.id = NEW.family_id;
                    IF new_family_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_family_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            -- ============= SUBFAMILY sync (NEW en mig 052) =============
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.subfamily_id IS DISTINCT FROM NEW.subfamily_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.subfamily_id IS NOT NULL THEN
                    SELECT tn.id INTO old_subfamily_node
                    FROM subfamilies sf
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(sf.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'subfamily')
                    WHERE sf.id = OLD.subfamily_id;
                    IF old_subfamily_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_subfamily_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.subfamily_id IS NOT NULL THEN
                    SELECT tn.id INTO new_subfamily_node
                    FROM subfamilies sf
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(sf.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'subfamily')
                    WHERE sf.id = NEW.subfamily_id;
                    IF new_subfamily_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_subfamily_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            -- ============= PRODUCT_TYPE sync (NEW en mig 052) =============
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.type_id IS DISTINCT FROM NEW.type_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.type_id IS NOT NULL THEN
                    SELECT tn.id INTO old_type_node
                    FROM product_types pt
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(pt.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'product_type')
                    WHERE pt.id = OLD.type_id;
                    IF old_type_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_type_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.type_id IS NOT NULL THEN
                    SELECT tn.id INTO new_type_node
                    FROM product_types pt
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(pt.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'product_type')
                    WHERE pt.id = NEW.type_id;
                    IF new_type_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_type_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_product_fk_to_registry
        AFTER INSERT OR UPDATE OF series_id, material_id, family_id, subfamily_id, type_id ON products
        FOR EACH ROW EXECUTE FUNCTION sync_product_fk_to_registry();
        """
    )


def downgrade() -> None:
    # Restaurar trigger original (sólo series/material) — replica mig 050.
    op.execute("DROP TRIGGER IF EXISTS trg_sync_product_fk_to_registry ON products;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_product_fk_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            old_series_node UUID;
            new_series_node UUID;
            old_material_node UUID;
            new_material_node UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.series_id IS DISTINCT FROM NEW.series_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.series_id IS NOT NULL THEN
                    SELECT tn.id INTO old_series_node
                    FROM series s
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(s.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
                    WHERE s.id = OLD.series_id;
                    IF old_series_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_series_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.series_id IS NOT NULL THEN
                    SELECT tn.id INTO new_series_node
                    FROM series s
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(s.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
                    WHERE s.id = NEW.series_id;
                    IF new_series_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_series_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.material_id IS DISTINCT FROM NEW.material_id) THEN
                IF TG_OP = 'UPDATE' AND OLD.material_id IS NOT NULL THEN
                    SELECT tn.id INTO old_material_node
                    FROM materials m
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(m.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'material')
                    WHERE m.id = OLD.material_id;
                    IF old_material_node IS NOT NULL THEN
                        DELETE FROM product_taxonomy_links
                        WHERE product_sku = NEW.sku AND node_id = old_material_node AND role = 'belongs_to';
                    END IF;
                END IF;

                IF NEW.material_id IS NOT NULL THEN
                    SELECT tn.id INTO new_material_node
                    FROM materials m
                    JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(m.code)
                        AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'material')
                    WHERE m.id = NEW.material_id;
                    IF new_material_node IS NOT NULL THEN
                        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                        VALUES (NEW.sku, new_material_node, 'belongs_to')
                        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                    END IF;
                END IF;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_product_fk_to_registry
        AFTER INSERT OR UPDATE OF series_id, material_id ON products
        FOR EACH ROW EXECUTE FUNCTION sync_product_fk_to_registry();
        """
    )

    # Drop nuevos triggers + funciones (mig 052)
    op.execute("DROP TRIGGER IF EXISTS trg_sync_product_types_to_registry ON product_types;")
    op.execute("DROP FUNCTION IF EXISTS sync_product_types_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_subfamilies_to_registry ON subfamilies;")
    op.execute("DROP FUNCTION IF EXISTS sync_subfamilies_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_families_to_registry ON families;")
    op.execute("DROP FUNCTION IF EXISTS sync_families_to_registry();")

    # Borrar data backfilled (skip sync loops)
    op.execute("SET LOCAL app.taxonomy_sync_skip = 'true';")
    op.execute(
        """
        DELETE FROM product_taxonomy_links
        WHERE node_id IN (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt ON tt.id = tn.type_id
            WHERE tt.slug IN ('family', 'subfamily', 'product_type')
        );
        """
    )
    op.execute(
        """
        DELETE FROM taxonomy_node_parents
        WHERE node_id IN (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt ON tt.id = tn.type_id
            WHERE tt.slug IN ('subfamily', 'product_type')
        );
        """
    )
    op.execute(
        """
        DELETE FROM taxonomy_nodes
        WHERE type_id IN (
            SELECT id FROM taxonomy_types
            WHERE slug IN ('family', 'subfamily', 'product_type')
        );
        """
    )
    op.execute(
        """
        DELETE FROM taxonomy_types
        WHERE slug IN ('family', 'subfamily', 'product_type');
        """
    )
