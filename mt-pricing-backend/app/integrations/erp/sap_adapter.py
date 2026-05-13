"""SAP RFC Adapter — stub.

Configuración necesaria:
    SAP_HOST, SAP_SYSTEM_NUMBER, SAP_CLIENT, SAP_USER, SAP_PASSWORD
    Librería: pyrfc (pip install pyrfc) — requiere SAP NW RFC SDK

RFC Mapping:
    push_goods_receipt → BAPI_GOODSMVT_CREATE
        GOODSMVT_HEADER.PSTNG_DATE = event.received_at.date()
        GOODSMVT_ITEM[0].MATERIAL   = event.sku
        GOODSMVT_ITEM[0].PLANT      = "AE01"  (configurar)
        GOODSMVT_ITEM[0].ENTRY_QNT  = str(event.qty_received)
        GOODSMVT_ITEM[0].MOVE_TYPE  = "101"
        Returns: MATERIALDOCUMENT (external_ref)

    pull_purchase_orders → BAPI_PO_GET_LIST
        PURCHASING_ORGANIZATION = "ME01"  (configurar)
        VENDOR = supplier_code
        Returns: list[POImport]

    push_map_update → No hay RFC directo. Usar BAPI_MATERIAL_SAVEDATA
        con MARD-STPRS (standard price) o MBEW-VERPR (moving avg price)

    health_check → RFC_PING (conexión directa al gateway SAP)

Prerrequisitos: pyrfc (SAP NW RFC SDK) instalado en el contenedor backend.
No añadir a requirements.txt hasta US-INV-01-07.
"""

from __future__ import annotations

from datetime import datetime

from app.integrations.erp.adapter import ERPAdapter
from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent, POImport


class SAPAdapter(ERPAdapter):
    """Integración con SAP vía pyrfc (SAP NW RFC SDK). Pendiente US-INV-01-07.

    Ver docstring del módulo para el mapping RFC completo y la configuración
    de credenciales (SAP_HOST, SAP_SYSTEM_NUMBER, SAP_CLIENT, SAP_USER,
    SAP_PASSWORD) en ``app/core/config.py``.
    """

    async def push_goods_receipt(self, event: GoodsReceivedEvent) -> str:
        raise NotImplementedError("SAPAdapter: configure SAP RFC connection")

    async def pull_purchase_orders(self, since: datetime) -> list[POImport]:
        raise NotImplementedError("SAPAdapter: configure SAP RFC connection")

    async def push_map_update(self, event: MAPUpdatedEvent) -> None:
        raise NotImplementedError("SAPAdapter: configure SAP RFC connection")

    async def health_check(self) -> bool:
        raise NotImplementedError("SAPAdapter: configure SAP RFC connection")
