"""API v1 router aggregator.

Wave 2 (Auth): registramos `auth`, `users`, `roles`. Más dominios se
añaden en sprints posteriores siguiendo la misma convención: cada submódulo
expone `router: APIRouter` y aquí se incluye con `router.include_router(...)`.
"""

from fastapi import APIRouter

from app.api.routes import (
    admin_calibrator,
    admin_flags,
    audit,
    audit_query,
    auth,
    channels_mirror,
    costs,
    currencies,
    dashboard,
    fx_rates,
    graphrag,
    imports,
    imports_costs,
    imports_datasheets,
    imports_materials,
    jobs,
    matches,
    pricing,
    pricing_admin,
    pricing_engine,
    products,
    roles,
    suppliers,
    translations_workflow,
    users,
    vocabularies,
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
