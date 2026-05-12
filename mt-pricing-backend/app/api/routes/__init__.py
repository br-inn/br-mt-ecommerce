"""API v1 router aggregator.

Wave 2 (Auth): registramos `auth`, `users`, `roles`. Más dominios se
añaden en sprints posteriores siguiendo la misma convención: cada submódulo
expone `router: APIRouter` y aquí se incluye con `router.include_router(...)`.
"""

from fastapi import APIRouter

from app.api.routes import (
    admin_calibrator,
    admin_flags,
    asset_links,
    attributes,
    audit,
    audit_query,
    auth,
    channels_mirror,
    costs,
    currencies,
    dashboard,
    dimensions,
    documents,
    dr_drills,
    exception_rules,
    fx_rates,
    graphrag,
    human_queue,
    imports,
    imports_costs,
    imports_datasheets,
    imports_materials,
    jobs,
    matches,
    parallel_run,
    pricing,
    pricing_admin,
    pricing_dashboard,
    pricing_engine,
    products,
    roles,
    suppliers,
    translations_workflow,
    users,
    vocabularies,
)
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
