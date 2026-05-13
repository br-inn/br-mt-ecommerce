"""Odoo JSON-RPC Adapter — stub.

Configuración necesaria:
    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
    Protocolo: xmlrpc.client (stdlib) o odoorpc (pip)

API Mapping:
    push_goods_receipt → models.execute_kw(db, uid, pwd,
        'stock.picking', 'create', [{'picking_type_id': 1, ...}])
        Confirmar con: 'button_validate'
        Returns: picking_id (external_ref)

    pull_purchase_orders → models.execute_kw(db, uid, pwd,
        'purchase.order', 'search_read',
        [[['state','in',['purchase','done']], ['date_approve','>=', since]]])
        Returns: list[POImport]

    push_map_update → models.execute_kw(db, uid, pwd,
        'product.product', 'write',
        [[product_id], {'standard_price': float(event.map_after)}])

    health_check → xmlrpc.client ServerProxy(ODOO_URL + '/xmlrpc/2/common')
        .version() → {'server_version': '17.0', ...}

Prerrequisitos: odoorpc (pip install odoorpc) o xmlrpc.client (stdlib).
No añadir a requirements.txt hasta US-INV-01-07.
"""

from __future__ import annotations

from datetime import datetime

from app.integrations.erp.adapter import ERPAdapter
from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent, POImport


class OdooAdapter(ERPAdapter):
    """Integración con Odoo vía JSON-RPC. Pendiente US-INV-01-07.

    Ver docstring del módulo para el mapping API completo y la configuración
    de credenciales (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    en ``app/core/config.py``.
    """

    async def push_goods_receipt(self, event: GoodsReceivedEvent) -> str:
        raise NotImplementedError("OdooAdapter: configure Odoo JSON-RPC")

    async def pull_purchase_orders(self, since: datetime) -> list[POImport]:
        raise NotImplementedError("OdooAdapter: configure Odoo JSON-RPC")

    async def push_map_update(self, event: MAPUpdatedEvent) -> None:
        raise NotImplementedError("OdooAdapter: configure Odoo JSON-RPC")

    async def health_check(self) -> bool:
        raise NotImplementedError("OdooAdapter: configure Odoo JSON-RPC")
