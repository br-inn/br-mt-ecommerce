"""API v1 router aggregator.

Wave 2 (Auth): registramos `auth`, `users`, `roles`. Más dominios se
añaden en sprints posteriores siguiendo la misma convención: cada submódulo
expone `router: APIRouter` y aquí se incluye con `router.include_router(...)`.
"""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    admin_calibrator,
    admin_erp,
    admin_erp_eventos,
    admin_flags,
    admin_manufacturers,
    admin_pim_quality,
    admin_price_calibration,
    asset_links,
    attributes,
    audit,
    audit_query,
    auth,
    channels,
    channels_mirror,
    costs,
    currencies,
    dashboard,
    dimensions,
    documents,
    dr_drills,
    exception_rules,
    exports,
    fx_rates,
    goods_receipts,
    graphrag,
    human_queue,
    inventory,
    imports,
    imports_costs,
    imports_datasheets,
    imports_materials,
    internal_cdc,
    jobs,
    matches,
    parallel_run,
    pricing,
    pricing_admin,
    pricing_dashboard,
    pricing_engine,
    procurement,
    products,
    purchase_orders,
    roles,
    suppliers,
    translations_workflow,
    users,
    vocabularies,
    warehouses,
)
from app.api.routes.matches import dataset_router as comparator_dataset_router
from app.api.routes.documents import admin_router as admin_documents_router
from app.api.routes.attributes import (
    admin_attributes_router,
    products_attributes_router,
)
from app.api.routes.costs import products_costs_router
from app.api.routes.products_display import products_display_router
from app.api.routes.taxonomy_extras import (
    admin_divisions_router,
    admin_materials_router,
    admin_series_router,
    divisions_router,
    materials_router,
    products_divisions_router,
    series_router,
)
from app.api.routes.taxonomy_registry import (
    admin_family_schemas_router,
    admin_products_taxonomies_router,
    admin_registry_router,
    products_taxonomies_router,
    registry_router,
)
from app.api.routes.vocabularies import (
    admin_vocab_router,
    products_vocab_router,
    taxonomy_router,
)

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(roles.router)
router.include_router(products.router)
router.include_router(suppliers.router)
router.include_router(imports.router)
router.include_router(dashboard.router)
router.include_router(pricing.router)
router.include_router(costs.router)
router.include_router(jobs.router)
router.include_router(audit.router)
router.include_router(matches.router)
router.include_router(channels_mirror.router)
router.include_router(channels.router)
router.include_router(currencies.router)
router.include_router(fx_rates.router)
router.include_router(imports_costs.router)
router.include_router(imports_materials.router)
router.include_router(translations_workflow.router)
router.include_router(products_costs_router)
router.include_router(audit_query.router)
router.include_router(pricing_engine.router)
router.include_router(imports_datasheets.router)
router.include_router(graphrag.router)
router.include_router(admin_flags.router)
router.include_router(admin_calibrator.router)
router.include_router(pricing_admin.router)
router.include_router(exception_rules.router)
router.include_router(vocabularies.router)
router.include_router(admin_vocab_router)
router.include_router(products_vocab_router, prefix="/products")
router.include_router(taxonomy_router)
# Stage 3 — divisions, series rica, materials (Wave 11)
router.include_router(divisions_router)
router.include_router(series_router)
router.include_router(materials_router)
router.include_router(admin_divisions_router)
router.include_router(admin_series_router)
router.include_router(admin_materials_router)
router.include_router(products_divisions_router, prefix="/products")
router.include_router(products_display_router, prefix="/products")
# Sprint 7 — Registry polimórfico (migs 049/050)
router.include_router(registry_router)
router.include_router(products_taxonomies_router)
router.include_router(admin_registry_router)
router.include_router(admin_products_taxonomies_router)
router.include_router(admin_family_schemas_router)
# Fase 2 — EAV typed attributes (migs. 054/055/056)
router.include_router(attributes.router)
router.include_router(admin_attributes_router)
router.include_router(products_attributes_router, prefix="/products")
# Fase 4 — polymorphic asset_links + versioned documents (migs. 058/059/060)
router.include_router(asset_links.router)
router.include_router(documents.router)
router.include_router(admin_documents_router)
# Fase 3 — tablas técnicas granulares (migs. 061/062/063)
router.include_router(dimensions.router)
router.include_router(dimensions.admin_router)
# Sprint 7 — Parallel run report (US-1B-05-01)
router.include_router(parallel_run.router)
# US-RND-01-10 — Human Queue validación humana
router.include_router(human_queue.router)
# US-DR-DRILLS — Disaster Recovery drills (mig. 076)
router.include_router(dr_drills.router)
# US-1B-05-07 — Pricing observability dashboard
router.include_router(pricing_dashboard.router)
# US-1B-04-02 — Exports CSV por canal (solo approved/auto_approved)
router.include_router(exports.router)
# US-F15-01-03 — CDC Postgres → Neo4j (Supabase Realtime → Celery → Cypher)
router.include_router(internal_cdc.router)
# US-F15-03-01 — Dataset export etiquetado (labeled pairs JSONL)
router.include_router(comparator_dataset_router)
# PIM Data Quality diagnostics
router.include_router(admin_pim_quality.router)
# US-F15-02-03 — Manufacturers whitelist (RIS boost) admin CRUD
router.include_router(admin_manufacturers.router)
# US-F15-02-04 — Price calibration ranges CRUD + import/export + recalibrate trigger
router.include_router(admin_price_calibration.router)
# EP-INV-01 — Purchase Orders CRUD (US-INV-01-03)
router.include_router(purchase_orders.router)
# EP-INV-01 — Goods Receipts (US-INV-01-04)
router.include_router(goods_receipts.router)
# EP-INV-01 — Inventory Positions Dashboard (US-INV-01-05)
router.include_router(inventory.router)
# US-INV-01-08 — Admin seed/maintenance endpoints
router.include_router(admin.router)
# US-INV-01-06 — ERP adapter health check
router.include_router(admin_erp.router)
# US-INV-01-07 — ERP sync events log + retry
router.include_router(admin_erp_eventos.router)
router.include_router(warehouses.router)
router.include_router(procurement.router)
