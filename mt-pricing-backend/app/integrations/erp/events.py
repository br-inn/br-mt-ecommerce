"""Dataclasses de eventos para el ERP Adapter Layer (EP-INV-01).

Estas estructuras son el contrato entre el sistema interno y cualquier ERP
externo (SAP, Odoo, etc.). Los campos reflejan el mínimo necesario para
los flujos GR → MAP y PO sync de la Fase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class GoodsReceivedEvent:
    """Evento emitido cuando se registra una recepción de mercancía (GR).

    ``mt_system_ref`` se genera como ``"MT-GR-{gr_id[:8]}"`` y sirve como
    referencia externa que el ERP puede usar para correlacionar el documento.
    """

    gr_id: str
    po_number: str
    sku: str
    supplier_code: str
    scheme_code: str
    qty_received: Decimal
    actual_unit_price: Decimal
    actual_breakdown: dict
    map_before: Decimal | None
    map_after: Decimal
    received_at: datetime
    mt_system_ref: str  # "MT-GR-{gr_id[:8]}"


@dataclass
class MAPUpdatedEvent:
    """Evento emitido cuando el MAP Engine actualiza el precio de coste medio (MAP)."""

    sku: str
    supplier_code: str
    scheme_code: str
    map_before: Decimal | None
    map_after: Decimal
    triggered_by_gr_id: str
    updated_at: datetime


@dataclass
class POLineImport:
    """Línea de una Purchase Order importada desde un ERP externo."""

    sku: str
    scheme_code: str
    qty_ordered: Decimal
    unit_price: Decimal
    landed_cost_breakdown: dict = field(default_factory=dict)


@dataclass
class POImport:
    """Purchase Order importada desde un ERP externo."""

    erp_po_number: str
    supplier_code: str
    currency: str
    lines: list[POLineImport] = field(default_factory=list)
