"""Re-export todos los modelos ORM para que Alembic los registre via Base.metadata.

⚠ Nuevos modelos: añadir el import + el nombre en `__all__`. Si no, Alembic
no los descubre y las migraciones autogenerate los ignoran.
"""

from __future__ import annotations

from app.db.models.audit import AuditEvent
from app.db.models.compatibility import ProductCompatibility
from app.db.models.components import ProductConnection, ProductMaterial
from app.db.models.tech_tables import ProductTechTable
from app.db.models.cdc_event import CdcEvent
from app.db.models.channel_listing import ChannelListing, ChannelSyncEvent
from app.db.models.cost import Cost  # US-1A-04-02 — moved from pricing.py
from app.db.models.cost_scheme import CostScheme
from app.db.models.currency import Currency
from app.db.models.datasheet_import_run import ProductDatasheet
from app.db.models.feature_flag import FeatureFlag
from app.db.models.golden_label import CalibratorVersion, GoldenLabel
from app.db.models.import_run import ImportRun
from app.db.models.job import JobDefinition, JobRun
from app.db.models.match_candidate import MatchCandidate
from app.db.models.material_compatibility import MaterialCompatibility
from app.db.models.notification import Notification
from app.db.models.pricing import (
    Channel,
    ExceptionRule,
    FXRate,
    Price,
    PriceApprovalEvent,
)
from app.db.models.product import Product, ProductImage, ProductTranslation
from app.db.models.supplier import Supplier
from app.db.models.user import Permission, Role, RolePermission, User
from app.db.models.vocabularies import (
    Application,
    Brand,
    Certification,
    Division,
    Family,
    Material,
    ProductApplication,
    ProductCertification,
    ProductDivision,
    ProductType,
    Series,
    SeriesCertification,
    SeriesDivision,
    SeriesTier,
    SeriesTranslation,
    Subfamily,
)

__all__ = [
    # users / auth
    "User",
    "Role",
    "Permission",
    "RolePermission",
    # products
    "Product",
    "ProductTranslation",
    "ProductImage",
    # master data fase 1a
    "Currency",
    "Supplier",
    "CostScheme",
    # audit
    "AuditEvent",
    # jobs / scheduler
    "JobDefinition",
    "JobRun",
    # imports (US-1A-06-01)
    "ImportRun",
    # pricing engine (Wave 2 — motor v5.1)
    "Channel",
    "FXRate",
    "Cost",
    "Price",
    "ExceptionRule",
    "PriceApprovalEvent",
    # matching pipeline (Sprint 3 — US-1A-09-01)
    "MatchCandidate",
    # channel mirror (Sprint 3 — US-1A-09-02)
    "ChannelListing",
    "ChannelSyncEvent",
    # importer materials (Sprint 3 — US-1A-06-03)
    "MaterialCompatibility",
    # importer datasheets PDF (Sprint 4 — US-1A-06-04)
    "ProductDatasheet",
    # graphrag CDC outbox (Sprint 4 — US-RND-01-11)
    "CdcEvent",
    # feature flags + kill-switch (Sprint 5 — US-1A-09-08)
    "FeatureFlag",
    # calibrator training pipeline (Sprint 5 — US-1A-09-07)
    "GoldenLabel",
    "CalibratorVersion",
    # notifications inbox (Sprint 6 — US-1B-02-08)
    "Notification",
    # Wave 4 — vocabularios M:N
    "Certification",
    "Application",
    "ProductCertification",
    "ProductApplication",
    # Stage 1 Opción C — taxonomía (mig. 042)
    "Brand",
    "Family",
    "Subfamily",
    "ProductType",
    # Stage 3 — divisions, series rica, materials (migs. 044/045/046)
    "Division",
    "ProductDivision",
    "SeriesTier",
    "Series",
    "SeriesTranslation",
    "SeriesDivision",
    "SeriesCertification",
    "Material",
    # Wave 7 — spare parts / accessories compatibility M:N
    "ProductCompatibility",
    # Wave 3 — multi-component (materials + connections)
    "ProductMaterial",
    "ProductConnection",
    # Wave 6 — tech tables (matrix-style)
    "ProductTechTable",
]
