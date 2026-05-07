"""API v1 router aggregator.

Wave 2 (Auth): registramos `auth`, `users`, `roles`. Más dominios se
añaden en sprints posteriores siguiendo la misma convención: cada submódulo
expone `router: APIRouter` y aquí se incluye con `router.include_router(...)`.
"""

from fastapi import APIRouter

from app.api.routes import (
    audit,
    auth,
    channels_mirror,
    costs,
    currencies,
    dashboard,
    fx_rates,
    imports,
    imports_costs,
    imports_materials,
    jobs,
    matches,
    pricing,
    products,
    roles,
    suppliers,
    translations_workflow,
    users,
)
from app.api.routes.costs import products_costs_router

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
