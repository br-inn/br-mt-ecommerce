-- =============================================================================
-- clean_test_data.sql
-- Borra TODOS los datos de negocio/prueba y deja la BD en estado limpio.
-- Preserva: master data (currencies, channels, schemes, brands, families,
--   subfamilies, suppliers, fx_rates, exception_rules, job_definitions,
--   feature_flags, roles, permissions, users, materials, standards,
--   divisions, series, gl_accounts, posting_periods, cost/profit centers,
--   warehouses/zones/locations, taxonomy, EAV definitions, vocabularios).
--
-- Uso:
--   psql $DATABASE_URL -f scripts/clean_test_data.sql
--   o desde psql: \i scripts/clean_test_data.sql
--
-- ADVERTENCIA: irreversible. Solo usar en entornos de desarrollo/prueba.
-- =============================================================================

BEGIN;

-- Desactivar triggers que bloquearían el truncate (ej. status inicial de prices)
ALTER TABLE prices DISABLE TRIGGER prices_initial_status_trg;

-- =============================================================================
-- 1. FINANCE & BILLING
--    Hijos primero para respetar FKs sin necesitar CASCADE en cada tabla.
-- =============================================================================
TRUNCATE TABLE
    e_invoice_submissions,
    dunning_history,
    tax_provisions,
    period_close_checklists,
    journal_entry_controls,
    financial_entries,
    journal_entries,
    payment_promises,
    payment_run_items,
    payment_runs,
    vendor_open_items,
    vendor_invoices,
    customer_open_items,
    customer_credit_limits,
    invoice_lines,
    invoices,
    standard_costs,
    budgets
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 2. VENTAS & ENTREGAS (O2C)
-- =============================================================================
TRUNCATE TABLE
    rma_lines,
    credit_memos,
    rma_headers,
    return_deliveries,
    outbound_delivery_lines,
    outbound_deliveries,
    sales_order_lines,
    sales_orders
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 3. COMPRAS & APROVISIONAMIENTO (P2P)
-- =============================================================================
TRUNCATE TABLE
    rfq_vendor_responses,
    rfq_lines,
    rfq_headers,
    source_list,
    goods_receipts,
    purchase_order_lines,
    purchase_orders
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 4. INVENTARIO
-- =============================================================================
TRUNCATE TABLE
    stock_reservations,
    stock_movements,
    inventory_alerts,
    cycle_counts,
    cycle_count_schedules,
    product_abc_classifications,
    replenishment_params,
    inventory_lots,
    cost_lots,
    inventory_positions
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 5. PRICING, MATCHING & SCRAPER
-- =============================================================================
TRUNCATE TABLE
    hitl_queue,
    price_alerts,
    price_variances,
    price_reference_excel,
    price_history_raw,
    match_decisions,
    match_rule_stats,
    rule_suggestions,
    unmatched_offers,
    competitor_listings,
    competitor_fetch_errors,
    competitor_brands,
    golden_labels,
    calibrator_versions,
    scraper_brand_extractors,
    match_candidates,
    price_approval_events,
    prices,
    costs
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 6. MARKETPLACE & CANALES
-- =============================================================================
TRUNCATE TABLE
    channel_state_history,
    channel_sync_events,
    channel_listings,
    product_marketplace_listings
RESTART IDENTITY CASCADE;

-- =============================================================================
-- 7. CATÁLOGO DE PRODUCTO
--    Dependencias internas: hijos antes de padres.
-- =============================================================================
TRUNCATE TABLE
    attribute_values,
    asset_links,
    product_applications,
    product_taxonomy_links,
    product_compatibility,
    product_materials,
    product_divisions,
    product_certifications,
    series_certifications,
    certificate_scopes,
    certificates,
    product_bore_dimensions,
    product_datasheets,
    product_tech_tables,
    product_equivalences,
    product_search_queries,
    product_uom_conversions,
    product_releases,
    model_dimension_rows,
    model_flow_data,
    model_tech_tables,
    product_models,
    product_assets,
    product_translations
RESTART IDENTITY CASCADE;

-- products al final: es padre de casi todo lo de arriba
TRUNCATE TABLE products RESTART IDENTITY CASCADE;

-- =============================================================================
-- 8. OPERACIONES / AUDIT / EVENTOS
-- =============================================================================
TRUNCATE TABLE
    kg_integrity_results,
    dr_drills,
    last_good_exports,
    exports_manifest,
    import_runs,
    job_runs,
    erp_sync_events,
    cdc_events,
    notifications
RESTART IDENTITY CASCADE;

-- =============================================================================
-- Re-activar triggers
-- =============================================================================
ALTER TABLE prices ENABLE TRIGGER prices_initial_status_trg;

COMMIT;
