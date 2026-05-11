"""taxonomy_backfill_sync — backfill registry desde legacy + sync triggers.

Segunda capa de E1-hardened. Una vez que mig. 049 creó las 7 tablas del
registry polimórfico, esta migración:

1. Backfill inicial (idempotente, ON CONFLICT DO NOTHING):
   - Cada fila de ``divisions`` → ``taxonomy_nodes`` (type='division')
   - Cada fila de ``series_tiers`` → ``taxonomy_nodes`` (type='tier')
   - Cada fila de ``series`` → ``taxonomy_nodes`` (type='series'),
     con parent_id apuntando al tier correspondiente (cuando series.tier_id no es NULL)
   - Cada fila de ``materials`` → ``taxonomy_nodes`` (type='material')

2. Backfill de ``product_taxonomy_links`` (role='belongs_to'):
   - Desde ``product_divisions`` (M:N)
   - Desde ``products.series_id`` cuando no es NULL
   - Desde ``products.material_id`` cuando no es NULL

3. Sync triggers one-way (legacy → registry) para mantener registro consistente
   mientras código existente sigue escribiendo a tablas legacy. Las divisiones
   son source of truth; el registry es vista derivada hasta migración de
   código consumidor (PR futuro).

   Tablas con triggers:
   - divisions → taxonomy_nodes (type='division')
   - series_tiers → taxonomy_nodes (type='tier')
   - series → taxonomy_nodes (type='series') + parent_id desde tier_id
   - materials → taxonomy_nodes (type='material')
   - product_divisions → product_taxonomy_links
   - products (UPDATE de series_id/material_id) → product_taxonomy_links

Loop prevention: cada trigger chequea ``app.taxonomy_sync_skip`` session var
y la setea durante su trabajo. Triggers reversos (registry → legacy) NO se
crean en este PR; eso requiere refactor de consumidores legacy.

NOTA sobre slugs: las tablas legacy usan ``code`` como identificador. Para
mapeo 1-a-1 con ``taxonomy_nodes.slug`` (regex `^[a-z][a-z0-9_]*$`),
normalizamos: lowercase + replace `-` y espacios con `_`. Si el código
legacy ya cumple el regex, se preserva tal cual.

Revision ID: 20260511_050
Revises: 20260511_049
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260511_050"
down_revision: str | None = "20260511_049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Función SQL helper para normalizar code legacy → slug válido del registry.
_NORMALIZE_SLUG_FN = """
CREATE OR REPLACE FUNCTION taxonomy_normalize_slug(input_text TEXT)
RETURNS TEXT AS $$
DECLARE
    result TEXT;
BEGIN
    -- lowercase + reemplaza no-alphanumeric con _ + colapsa _ repetidos
    result := lower(input_text);
    result := regexp_replace(result, '[^a-z0-9_]+', '_', 'g');
    result := regexp_replace(result, '_+', '_', 'g');
    result := trim(both '_' from result);
    -- prefijar con 'n_' si empieza con dígito (regex registry requiere letra inicial)
    IF result ~ '^[0-9]' THEN
        result := 'n_' || result;
    END IF;
    -- fallback si quedó vacío
    IF result = '' OR result IS NULL THEN
        result := 'unnamed';
    END IF;
    RETURN result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. Helper function: normalize legacy code → registry-valid slug
    # ------------------------------------------------------------------
    op.execute(_NORMALIZE_SLUG_FN)

    # ------------------------------------------------------------------
    # 1. Backfill taxonomy_nodes desde divisions
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active)
        SELECT
            tt.id AS type_id,
            taxonomy_normalize_slug(d.code) AS slug,
            jsonb_build_object('es', d.name, 'en', d.name) AS labels,
            d.sort_order AS display_order,
            d.active
        FROM divisions d
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'division'
        ) tt
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 2. Backfill taxonomy_nodes desde series_tiers
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
        SELECT
            tt.id AS type_id,
            taxonomy_normalize_slug(st.code) AS slug,
            jsonb_build_object('es', st.name, 'en', st.name) AS labels,
            st.rank AS display_order,
            st.active,
            jsonb_build_object('display_color', st.display_color, 'rank', st.rank)
        FROM series_tiers st
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'tier'
        ) tt
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 3. Backfill taxonomy_nodes desde series (con parent = tier asociado)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (
            type_id, slug, labels, display_order, active, attributes, parent_id
        )
        SELECT
            tt_series.id AS type_id,
            taxonomy_normalize_slug(s.code) AS slug,
            jsonb_build_object('es', s.name_en, 'en', s.name_en) AS labels,
            s.sort_order AS display_order,
            s.active,
            jsonb_build_object(
                'pressure_rating_pn', s.pressure_rating_pn,
                'temperature_min_c', s.temperature_min_c,
                'temperature_max_c', s.temperature_max_c,
                'banner_color', s.banner_color,
                'hero_image_url', s.hero_image_url,
                'features_tags', s.features_tags
            ) AS attributes,
            tier_node.id AS parent_id
        FROM series s
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'series'
        ) tt_series
        LEFT JOIN series_tiers st ON st.id = s.tier_id
        LEFT JOIN LATERAL (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt ON tt.id = tn.type_id
            WHERE tt.slug = 'tier'
              AND tn.slug = taxonomy_normalize_slug(st.code)
            LIMIT 1
        ) tier_node ON true
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # Backfill closure: series con tier parent → taxonomy_node_parents
    # (el trigger de closure se dispara al insertar aquí)
    op.execute(
        """
        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
        SELECT s_node.id, t_node.id, true
        FROM series s
        JOIN series_tiers st ON st.id = s.tier_id
        JOIN taxonomy_nodes s_node ON s_node.slug = taxonomy_normalize_slug(s.code)
            AND s_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
        JOIN taxonomy_nodes t_node ON t_node.slug = taxonomy_normalize_slug(st.code)
            AND t_node.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'tier')
        WHERE s.tier_id IS NOT NULL
        ON CONFLICT (node_id, parent_id) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 4. Backfill taxonomy_nodes desde materials
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
        SELECT
            tt.id AS type_id,
            taxonomy_normalize_slug(m.code) AS slug,
            jsonb_build_object('es', m.name, 'en', m.name) AS labels,
            m.sort_order AS display_order,
            m.active,
            jsonb_build_object('family_kind', m.family_kind, 'notes', m.notes)
        FROM materials m
        CROSS JOIN LATERAL (
            SELECT id FROM taxonomy_types WHERE slug = 'material'
        ) tt
        ON CONFLICT (type_id, slug) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 5. Backfill product_taxonomy_links desde product_divisions (M:N)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT pd.product_sku, tn.id, 'belongs_to'
        FROM product_divisions pd
        JOIN divisions d ON d.id = pd.division_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(d.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'division')
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 6. Backfill product_taxonomy_links desde products.series_id
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT p.sku, tn.id, 'belongs_to'
        FROM products p
        JOIN series s ON s.id = p.series_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(s.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'series')
        WHERE p.series_id IS NOT NULL
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 7. Backfill product_taxonomy_links desde products.material_id
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO product_taxonomy_links (product_sku, node_id, role)
        SELECT p.sku, tn.id, 'belongs_to'
        FROM products p
        JOIN materials m ON m.id = p.material_id
        JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(m.code)
            AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'material')
        WHERE p.material_id IS NOT NULL
        ON CONFLICT (product_sku, node_id, role) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 8. Sync triggers: legacy → registry (one-way)
    # ------------------------------------------------------------------
    # Helper: chequear si estamos dentro de un sync trigger (loop prevention).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION taxonomy_sync_should_skip()
        RETURNS BOOLEAN AS $$
        BEGIN
            RETURN COALESCE(current_setting('app.taxonomy_sync_skip', true), '') = 'true';
        END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    # --- divisions → taxonomy_nodes(type='division') ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_divisions_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            old_slug TEXT;
            new_slug TEXT;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'division';

            IF TG_OP = 'INSERT' THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active)
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.sort_order,
                    NEW.active
                )
                ON CONFLICT (type_id, slug) DO UPDATE
                SET labels = EXCLUDED.labels,
                    display_order = EXCLUDED.display_order,
                    active = EXCLUDED.active;

            ELSIF TG_OP = 'UPDATE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                new_slug := taxonomy_normalize_slug(NEW.code);
                UPDATE taxonomy_nodes
                SET slug = new_slug,
                    labels = jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    display_order = NEW.sort_order,
                    active = NEW.active
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

        CREATE TRIGGER trg_sync_divisions_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON divisions
        FOR EACH ROW EXECUTE FUNCTION sync_divisions_to_registry();
        """
    )

    # --- series_tiers → taxonomy_nodes(type='tier') ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_series_tiers_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            old_slug TEXT;
            new_slug TEXT;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'tier';

            IF TG_OP = 'INSERT' THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.rank,
                    NEW.active,
                    jsonb_build_object('display_color', NEW.display_color, 'rank', NEW.rank)
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
                    display_order = NEW.rank,
                    active = NEW.active,
                    attributes = jsonb_build_object('display_color', NEW.display_color, 'rank', NEW.rank)
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

        CREATE TRIGGER trg_sync_series_tiers_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON series_tiers
        FOR EACH ROW EXECUTE FUNCTION sync_series_tiers_to_registry();
        """
    )

    # --- series → taxonomy_nodes(type='series') + parent link ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_series_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            tier_type_id UUID;
            old_slug TEXT;
            new_slug TEXT;
            node_id_var UUID;
            tier_node_id UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'series';
            SELECT id INTO tier_type_id FROM taxonomy_types WHERE slug = 'tier';

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                new_slug := taxonomy_normalize_slug(NEW.code);

                -- Buscar tier_node si existe
                tier_node_id := NULL;
                IF NEW.tier_id IS NOT NULL THEN
                    SELECT tn.id INTO tier_node_id
                    FROM taxonomy_nodes tn
                    JOIN series_tiers st ON taxonomy_normalize_slug(st.code) = tn.slug
                    WHERE st.id = NEW.tier_id AND tn.type_id = tier_type_id;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO taxonomy_nodes (
                    type_id, slug, labels, display_order, active, attributes, parent_id
                )
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name_en, 'en', NEW.name_en),
                    NEW.sort_order,
                    NEW.active,
                    jsonb_build_object(
                        'pressure_rating_pn', NEW.pressure_rating_pn,
                        'temperature_min_c', NEW.temperature_min_c,
                        'temperature_max_c', NEW.temperature_max_c,
                        'banner_color', NEW.banner_color,
                        'features_tags', NEW.features_tags
                    ),
                    tier_node_id
                )
                ON CONFLICT (type_id, slug) DO UPDATE
                SET labels = EXCLUDED.labels,
                    display_order = EXCLUDED.display_order,
                    active = EXCLUDED.active,
                    attributes = EXCLUDED.attributes,
                    parent_id = EXCLUDED.parent_id
                RETURNING id INTO node_id_var;

                IF tier_node_id IS NOT NULL THEN
                    INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                    VALUES (node_id_var, tier_node_id, true)
                    ON CONFLICT (node_id, parent_id) DO UPDATE SET is_primary = true;
                END IF;

            ELSIF TG_OP = 'UPDATE' THEN
                old_slug := taxonomy_normalize_slug(OLD.code);
                UPDATE taxonomy_nodes
                SET slug = new_slug,
                    labels = jsonb_build_object('es', NEW.name_en, 'en', NEW.name_en),
                    display_order = NEW.sort_order,
                    active = NEW.active,
                    attributes = jsonb_build_object(
                        'pressure_rating_pn', NEW.pressure_rating_pn,
                        'temperature_min_c', NEW.temperature_min_c,
                        'temperature_max_c', NEW.temperature_max_c,
                        'banner_color', NEW.banner_color,
                        'features_tags', NEW.features_tags
                    ),
                    parent_id = tier_node_id
                WHERE type_id = type_id_var AND slug = old_slug
                RETURNING id INTO node_id_var;

                -- Si cambió el tier, actualizar taxonomy_node_parents
                IF node_id_var IS NOT NULL THEN
                    DELETE FROM taxonomy_node_parents
                    WHERE node_id = node_id_var AND is_primary = true;
                    IF tier_node_id IS NOT NULL THEN
                        INSERT INTO taxonomy_node_parents (node_id, parent_id, is_primary)
                        VALUES (node_id_var, tier_node_id, true)
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

        CREATE TRIGGER trg_sync_series_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON series
        FOR EACH ROW EXECUTE FUNCTION sync_series_to_registry();
        """
    )

    # --- materials → taxonomy_nodes(type='material') ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_materials_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            type_id_var UUID;
            old_slug TEXT;
            new_slug TEXT;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            SELECT id INTO type_id_var FROM taxonomy_types WHERE slug = 'material';

            IF TG_OP = 'INSERT' THEN
                new_slug := taxonomy_normalize_slug(NEW.code);
                INSERT INTO taxonomy_nodes (type_id, slug, labels, display_order, active, attributes)
                VALUES (
                    type_id_var,
                    new_slug,
                    jsonb_build_object('es', NEW.name, 'en', NEW.name),
                    NEW.sort_order,
                    NEW.active,
                    jsonb_build_object('family_kind', NEW.family_kind, 'notes', NEW.notes)
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
                    attributes = jsonb_build_object('family_kind', NEW.family_kind, 'notes', NEW.notes)
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

        CREATE TRIGGER trg_sync_materials_to_registry
        AFTER INSERT OR UPDATE OR DELETE ON materials
        FOR EACH ROW EXECUTE FUNCTION sync_materials_to_registry();
        """
    )

    # --- product_divisions → product_taxonomy_links ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_product_divisions_to_registry()
        RETURNS TRIGGER AS $$
        DECLARE
            node_id_var UUID;
        BEGIN
            IF taxonomy_sync_should_skip() THEN RETURN NULL; END IF;
            PERFORM set_config('app.taxonomy_sync_skip', 'true', true);

            IF TG_OP = 'INSERT' THEN
                SELECT tn.id INTO node_id_var
                FROM divisions d
                JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(d.code)
                    AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'division')
                WHERE d.id = NEW.division_id;

                IF node_id_var IS NOT NULL THEN
                    INSERT INTO product_taxonomy_links (product_sku, node_id, role)
                    VALUES (NEW.product_sku, node_id_var, 'belongs_to')
                    ON CONFLICT (product_sku, node_id, role) DO NOTHING;
                END IF;

            ELSIF TG_OP = 'DELETE' THEN
                SELECT tn.id INTO node_id_var
                FROM divisions d
                JOIN taxonomy_nodes tn ON tn.slug = taxonomy_normalize_slug(d.code)
                    AND tn.type_id = (SELECT id FROM taxonomy_types WHERE slug = 'division')
                WHERE d.id = OLD.division_id;

                IF node_id_var IS NOT NULL THEN
                    DELETE FROM product_taxonomy_links
                    WHERE product_sku = OLD.product_sku
                      AND node_id = node_id_var
                      AND role = 'belongs_to';
                END IF;
            END IF;

            PERFORM set_config('app.taxonomy_sync_skip', '', true);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_sync_product_divisions_to_registry
        AFTER INSERT OR DELETE ON product_divisions
        FOR EACH ROW EXECUTE FUNCTION sync_product_divisions_to_registry();
        """
    )

    # --- products.series_id / products.material_id UPDATE → links ---
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

            -- SERIES sync
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

            -- MATERIAL sync
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


def downgrade() -> None:
    # Drop triggers (reverse order)
    op.execute("DROP TRIGGER IF EXISTS trg_sync_product_fk_to_registry ON products;")
    op.execute("DROP FUNCTION IF EXISTS sync_product_fk_to_registry();")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_sync_product_divisions_to_registry ON product_divisions;"
    )
    op.execute("DROP FUNCTION IF EXISTS sync_product_divisions_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_materials_to_registry ON materials;")
    op.execute("DROP FUNCTION IF EXISTS sync_materials_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_series_to_registry ON series;")
    op.execute("DROP FUNCTION IF EXISTS sync_series_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_series_tiers_to_registry ON series_tiers;")
    op.execute("DROP FUNCTION IF EXISTS sync_series_tiers_to_registry();")

    op.execute("DROP TRIGGER IF EXISTS trg_sync_divisions_to_registry ON divisions;")
    op.execute("DROP FUNCTION IF EXISTS sync_divisions_to_registry();")

    op.execute("DROP FUNCTION IF EXISTS taxonomy_sync_should_skip();")

    # Borrar data backfilled — sync de skip para no disparar triggers reversos
    op.execute("SET LOCAL app.taxonomy_sync_skip = 'true';")
    op.execute(
        """
        DELETE FROM product_taxonomy_links
        WHERE node_id IN (
            SELECT tn.id
            FROM taxonomy_nodes tn
            JOIN taxonomy_types tt ON tt.id = tn.type_id
            WHERE tt.slug IN ('division', 'series', 'tier', 'material')
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
            WHERE tt.slug = 'series'
        );
        """
    )
    op.execute(
        """
        DELETE FROM taxonomy_nodes
        WHERE type_id IN (
            SELECT id FROM taxonomy_types
            WHERE slug IN ('division', 'series', 'tier', 'material')
        );
        """
    )

    op.execute("DROP FUNCTION IF EXISTS taxonomy_normalize_slug(TEXT);")
