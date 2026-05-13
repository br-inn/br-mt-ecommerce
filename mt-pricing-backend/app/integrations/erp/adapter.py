"""ABC del ERP Adapter — contrato para todas las implementaciones concretas.

Cada ERP (SAP, Odoo, NetSuite, etc.) implementa esta interfaz. La factory
`get_erp_adapter()` selecciona la implementación en runtime vía `ERP_ADAPTER`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent, POImport


class ERPAdapter(ABC):
    """Interfaz de integración con el ERP externo."""

    @abstractmethod
    async def push_goods_receipt(self, event: GoodsReceivedEvent) -> str:
        """Envía un GR al ERP. Retorna el ID externo asignado por el ERP."""
        ...

    @abstractmethod
    async def pull_purchase_orders(self, since: datetime) -> list[POImport]:
        """Trae las POs modificadas desde `since` en el ERP externo."""
        ...

    @abstractmethod
    async def push_map_update(self, event: MAPUpdatedEvent) -> None:
        """Notifica al ERP el nuevo MAP calculado internamente."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica conectividad con el ERP. True = saludable."""
        ...
