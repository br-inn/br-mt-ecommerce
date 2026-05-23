"""Factory del ERP Adapter — selecciona la implementación vía settings.ERP_ADAPTER.

Singleton cacheado con `functools.lru_cache`. Para reemplazar el adapter en
tests, invalidar la cache con `get_erp_adapter.cache_clear()`.
"""

from __future__ import annotations

from functools import lru_cache

from app.integrations.erp.adapter import ERPAdapter


@lru_cache(maxsize=1)
def get_erp_adapter() -> ERPAdapter:
    """Retorna la instancia singleton del adapter configurado en ERP_ADAPTER."""
    from app.core.config import settings

    adapter_name = settings.ERP_ADAPTER.lower()

    if adapter_name == "noop":
        from app.integrations.erp.noop_adapter import NoOpAdapter

        return NoOpAdapter()

    if adapter_name == "sap":
        from app.integrations.erp.sap_adapter import SAPAdapter

        return SAPAdapter()

    if adapter_name == "odoo":
        from app.integrations.erp.odoo_adapter import OdooAdapter

        return OdooAdapter()

    raise ValueError(
        f"ERP_ADAPTER='{adapter_name}' no reconocido. Valores válidos: 'noop', 'sap', 'odoo'."
    )
