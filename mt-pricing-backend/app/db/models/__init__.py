"""Re-export todos los modelos ORM para que Alembic los registre via Base.metadata.

⚠ Nuevos modelos: añadir el import + el nombre en `__all__`. Si no, Alembic
no los descubre y las migraciones autogenerate los ignoran.
"""

from __future__ import annotations

from app.db.models.asset_links import AssetLink
from app.db.models.attributes import (
    AttributeDefinition,
    AttributeOption,
    AttributeValue,
    FamilyAttribute,
)
from app.db.models.audit import AuditEvent
from app.db.models.audit_hash_state import AuditHashState
from app.db.models.billing import (
    DunningHistory,
    DunningLevel,
    EInvoiceSubmission,
    Invoice,
    InvoiceLine,
    PaymentPromise,
)
from app.db.models.cdc_event import CdcEvent
from app.db.models.certificates import Certificate, CertificateScope
from app.db.models.channel_listing import ChannelListing, ChannelSyncEvent
from app.db.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    ChannelSchemeParams,
    PricingScenario,
    TradeRouteParams,
)
from app.db.models.channels import Channel, ChannelStateHistory
from app.db.models.comparator import (
    BrandExtractor,
    CompetitorBrand,
    CompetitorListing,
    ManufacturerWhitelist,
    MatchDecision,
)
from app.db.models.comparator_config import ComparatorConfig
from app.db.models.compatibility import ProductCompatibility
from app.db.models.components import ProductConnection, ProductMaterial
from app.db.models.cost import Cost  # US-1A-04-02 — moved from pricing.py
from app.db.models.cost_scheme import CostScheme
from app.db.models.currency import Currency
from app.db.models.datasheet_import_run import ProductDatasheet
from app.db.models.dimensions import (
    ActuationCode,
    DimensionCell,
    DimensionColumn,
    DimensionRow,
    PressureTemperaturePoint,
    Standard,
)
from app.db.models.documents import Document
from app.db.models.dr_drills import DrDrill
from app.db.models.exports import ExportManifest, LastGoodExport
from app.db.models.feature_flag import FeatureFlag
from app.db.models.finance import (
    Budget,
    CostCenter,
    FinancialEntry,
    GlAccount,
    JournalEntryControl,
    PaymentRun,
    PaymentRunItem,
    PeriodCloseChecklist,
    PostingPeriod,
    PriceVariance,
    ProfitCenter,
    StandardCost,
    TaxProvision,
    VendorOpenItem,
)
from app.db.models.force_logout_event import ForceLogoutEvent
from app.db.models.golden_label import CalibratorVersion, GoldenLabel
from app.db.models.graphrag import KgIntegrityResult
from app.db.models.hitl_queue import HitlQueue
from app.db.models.import_run import ImportRun
from app.db.models.inventory import (
    CostLot,
    CycleCountSchedule,
    ERPSyncEvent,
    ExpiryAlertThreshold,
    GoodsReceipt,
    InventoryAlert,
    InventoryLot,
    InventoryPosition,
    JournalEntry,
    ProductAbcClassification,
    PurchaseOrder,
    PurchaseOrderLine,
    ReplenishmentParam,
    StockMovement,
    StockMovementType,
    Warehouse,
    WarehouseLocation,
    WarehouseZone,
)
from app.db.models.job import JobDefinition, JobRun
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision
from app.db.models.match_candidate import MatchCandidate
from app.db.models.match_rule_stat import MatchRuleStat
from app.db.models.material_alias import MaterialAlias
from app.db.models.material_compatibility import MaterialCompatibility
from app.db.models.norm_equivalence import NormEquivalence
from app.db.models.notification import Notification
from app.db.models.price_alerts import PriceAlert
from app.db.models.price_history import PriceHistoryRaw
from app.db.models.price_reference_excel import PriceReferenceExcel
from app.db.models.price_state_transitions import PriceStateTransition
from app.db.models.pricing import (
    ExceptionRule,
    FXRate,
    Price,
    PriceApprovalEvent,
)
from app.db.models.pricing_golden_tiers import PricingGoldenTier
from app.db.models.procurement import (
    ApprovalDecision,
    ApprovalRule,
    InvoiceTolerance,
    PurchaseRequisition,
    RfqHeader,
    RfqLine,
    RfqVendorResponse,
    SourceList,
    VendorInvoice,
    VendorProductCondition,
)
from app.db.models.product import (
    DnNpsReference,
    Product,
    ProductBoreDimension,
    ProductImage,
    ProductRelease,
    ProductTranslation,
    ProductUomConversion,
)
from app.db.models.product_models import (
    ModelDimensionRow,
    ModelFlowData,
    ModelTechTable,
    ProductModel,
)
from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.sales import (
    AtpCheckingRule,
    CreditMemo,
    CustomerCreditLimit,
    CustomerOpenItem,
    OutboundDelivery,
    OutboundDeliveryLine,
    RmaHeader,
    RmaLine,
    SalesOrder,
    SalesOrderLine,
    StockReservation,
)
from app.db.models.scraper_sources import (
    ScraperSource,
    ScraperSourceRecipe,
    ScraperSourceTestRun,
)
from app.db.models.search_query import ProductSearchQuery
from app.db.models.supplier import Supplier
from app.db.models.taxonomy_profile import TaxonomyProfile
from app.db.models.taxonomy_registry import (
    FamilySchema,
    ProductTaxonomyLink,
    TaxonomyAlias,
    TaxonomyNode,
    TaxonomyNodeDescendant,
    TaxonomyNodeParent,
    TaxonomyType,
)
from app.db.models.tech_tables import ProductTechTable
from app.db.models.unit_transform import UnitTransform
from app.db.models.unmatched_offer import UnmatchedOffer
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
    # M1-01 — product releases por mercado
    "ProductRelease",
    # M1-04 — UoM conversions por producto
    "ProductUomConversion",
    # DN/NPS norm lookup + bore dimensions by standard (mig. 099)
    "DnNpsReference",
    "ProductBoreDimension",
    # master data fase 1a
    "Currency",
    "Supplier",
    "CostScheme",
    # audit
    "AuditEvent",
    # audit hash chain singleton (mig. 076)
    "AuditHashState",
    # force-logout Realtime queue (ADR-032 — mig. 013)
    "ForceLogoutEvent",
    # jobs / scheduler
    "JobDefinition",
    "JobRun",
    # imports (US-1A-06-01)
    "ImportRun",
    # channel operational states (EP-1B-03 Sprint 8 — mig 079)
    "Channel",
    "ChannelStateHistory",
    # pricing engine (Wave 2 — motor v5.1)
    "FXRate",
    "Cost",
    "Price",
    "ExceptionRule",
    "PriceApprovalEvent",
    # matching pipeline (Sprint 3 — US-1A-09-01)
    "MatchCandidate",
    "UnmatchedOffer",
    # channel mirror (Sprint 3 — US-1A-09-02)
    "ChannelListing",
    "ChannelSyncEvent",
    # importer materials (Sprint 3 — US-1A-06-03)
    "MaterialCompatibility",
    # matching pipeline — material alias homologation (mig. 107)
    "MaterialAlias",
    # matching pipeline — LLM search query cache (mig. 123)
    "ProductSearchQuery",
    # importer datasheets PDF (Sprint 4 — US-1A-06-04)
    "ProductDatasheet",
    # graphrag CDC outbox (Sprint 4 — US-RND-01-11)
    "CdcEvent",
    # graphrag KG integrity results (Sprint 10 — US-F15-01-06)
    "KgIntegrityResult",
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
    # Sprint 7 — Registry polimórfico de taxonomías (mig. 049)
    "TaxonomyType",
    "TaxonomyNode",
    "TaxonomyNodeParent",
    "TaxonomyNodeDescendant",
    "TaxonomyAlias",
    "ProductTaxonomyLink",
    "FamilySchema",
    # Fase 2 — EAV typed attributes (migs. 054/055/056)
    "AttributeDefinition",
    "AttributeOption",
    "FamilyAttribute",
    "AttributeValue",
    # Fase 4 — polymorphic asset_links + versioned documents (migs. 058/059/060)
    "AssetLink",
    "Document",
    # Fase 3 — tablas técnicas granulares (migs. 061/062/063)
    "ActuationCode",
    "Standard",
    "DimensionColumn",
    "DimensionRow",
    "DimensionCell",
    "PressureTemperaturePoint",
    # Fase 1 hooks — comparator research workstream (mig. 069, ADR-012)
    "CompetitorBrand",
    "CompetitorListing",
    "MatchDecision",
    # US-SCR-05-01 — brand extractor LLM mapping (mig. 20260519_150)
    "BrandExtractor",
    # US-F15-02-03 — manufacturers whitelist para RIS boost (mig. 075)
    "ManufacturerWhitelist",
    # DR drills (mig. 076)
    "DrDrill",
    # Pricing exports manifest (US-1B-04-02 — mig. 081)
    "ExportManifest",
    # Last-known-good exports snapshot (US-1B-04-05 — mig. 083)
    "LastGoodExport",
    # Inventory costing pipeline (EP-INV-01 — migs. 090-094)
    "PurchaseOrder",
    "PurchaseOrderLine",
    "GoodsReceipt",
    "CostLot",
    "ERPSyncEvent",
    "InventoryPosition",
    "StockMovementType",
    "StockMovement",
    "JournalEntry",
    "InventoryLot",
    "Warehouse",
    "WarehouseZone",
    "WarehouseLocation",
    "PurchaseRequisition",
    "ApprovalDecision",
    "ApprovalRule",
    "VendorProductCondition",
    # EP-ERP-03 stories 04-06 (migs. 20260523_110-111)
    "VendorInvoice",
    "InvoiceTolerance",
    "SourceList",
    "RfqHeader",
    "RfqLine",
    "RfqVendorResponse",
    # EP-ERP-02 stories 05-08 (mig. 20260522_110)
    "ExpiryAlertThreshold",
    "InventoryAlert",
    "ReplenishmentParam",
    "ProductAbcClassification",
    "CycleCountSchedule",
    # EP-ERP-04 — Ventas O2C (migs. 20260524_110-114)
    "SalesOrder",
    "SalesOrderLine",
    "StockReservation",
    "AtpCheckingRule",
    "CustomerCreditLimit",
    "CustomerOpenItem",
    "OutboundDelivery",
    "OutboundDeliveryLine",
    "RmaHeader",
    "RmaLine",
    "CreditMemo",
    # EP-ERP-05 — Billing & Facturación (mig. 20260526_110)
    "Invoice",
    "InvoiceLine",
    "DunningLevel",
    "DunningHistory",
    "EInvoiceSubmission",
    "PaymentPromise",
    # EP-ERP-06 — Finanzas (migs. 20260527_110-118)
    "GlAccount",
    "PostingPeriod",
    "CostCenter",
    "ProfitCenter",
    "FinancialEntry",
    "VendorOpenItem",
    "PaymentRun",
    "PaymentRunItem",
    "StandardCost",
    "PriceVariance",
    "PeriodCloseChecklist",
    "TaxProvision",
    "JournalEntryControl",
    "Budget",
    # Product model hierarchy (plan 2026-05-15)
    "ProductModel",
    "ModelDimensionRow",
    "ModelFlowData",
    "ModelTechTable",
    "Certificate",
    "CertificateScope",
    # pricing state machine transition table (mig. 021)
    "PriceStateTransition",
    # pricing golden tiers v5.1 (mig. 021)
    "PricingGoldenTier",
    # parallel-run Excel reference prices (US-1B-05-01 — mig. 073)
    "PriceReferenceExcel",
    # EP-SCR-04 — price history raw scraping (US-SCR-04-01)
    "PriceHistoryRaw",
    # EP-SCR-04-05 — price alerts + pg_notify + heartbeat (US-SCR-04-05)
    "PriceAlert",
    # EP-SCR-04-08b — HITL queue uncertainty×value (US-SCR-04-08b)
    "HitlQueue",
    # Match Rule Engine — taxonomy profiles table (mig. 20260517_137)
    "TaxonomyProfile",
    # Match Rule Engine — comparator config + unit transforms (migs. 20260517_138-139)
    "ComparatorConfig",
    "UnitTransform",
    # Match Rule Engine — norm equivalences + rule stats + suggestions (migs. 20260517_140-142)
    "NormEquivalence",
    "MatchRuleStat",
    "RuleSuggestion",
    # Marketplace export listings (Task 1 migration)
    "MarketplaceListing",
    # Match Validation Agent — config singleton + decision log (Task 3)
    "MatchAgentConfig",
    "MatchAgentDecision",
    # Scraper Source Builder — motor configurable data-driven (Task 2)
    "ScraperSource",
    "ScraperSourceRecipe",
    "ScraperSourceTestRun",
    # Channel Pricing Engine (mig. 20260603_147)
    "TradeRouteParams",
    "ChannelFeeParams",
    "ChannelSchemeParams",
    "ChannelProductLogistics",
    "ChannelMarginTarget",
    "ChannelMarginOverride",
    "PricingScenario",
]
