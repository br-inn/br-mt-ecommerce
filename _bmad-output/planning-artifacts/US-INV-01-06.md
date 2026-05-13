# US-INV-01-06 — ERP Integration Adapter Layer (NoOp por defecto)

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 3 | **SP**: 8 | **Prioridad**: P1

## Contexto

Depende de US-INV-01-01 (stubs del adapter ya creados) y US-INV-01-02 (MAP Engine).
Esta story completa el adapter layer con los contratos formales y la infraestructura
de configuración. Los stubs `SAPAdapter` y `OdooAdapter` quedan funcionales con
`NotImplementedError` y documentación de los campos esperados por cada ERP.

El objetivo es que cuando el cliente conecte SAP/Oracle/NetSuite en el futuro,
un desarrollador solo tenga que:
1. Copiar `noop_adapter.py`, implementar los métodos
2. Cambiar `ERP_ADAPTER=sap` en el `.env`
3. No tocar nada del dominio

## Descripción

Completar el ERP adapter layer iniciado en US-INV-01-01 con:
- Contratos formales en los dataclasses de eventos
- `NoOpAdapter` con logging verbose para debugging
- Documentación inline en los stubs `SAPAdapter` / `OdooAdapter`
- Health check endpoint admin
- Tests del adapter pattern

## Criterios de Aceptación

### Contratos de eventos (`app/integrations/erp/events.py`)
- [ ] `GoodsReceivedEvent`:
  ```python
  @dataclass
  class GoodsReceivedEvent:
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
  ```
- [ ] `MAPUpdatedEvent`:
  ```python
  @dataclass
  class MAPUpdatedEvent:
      sku: str
      supplier_code: str
      scheme_code: str
      map_before: Decimal | None
      map_after: Decimal
      triggered_by_gr_id: str
      updated_at: datetime
  ```
- [ ] `POImport` (para pull de POs desde ERP):
  ```python
  @dataclass
  class POImport:
      erp_po_number: str
      supplier_code: str
      currency: str
      lines: list[POLineImport]

  @dataclass
  class POLineImport:
      sku: str
      scheme_code: str
      qty_ordered: Decimal
      unit_price: Decimal
      landed_cost_breakdown: dict
  ```

### NoOpAdapter (`app/integrations/erp/noop_adapter.py`)
- [ ] Implementa todos los métodos de `ERPAdapter`
- [ ] Cada método loguea en `INFO`: `"[ERP:NoOp] {method_name} called — adapter is no-op"`
      + dump del evento (json) si `settings.ERP_DEBUG = True`
- [ ] `push_goods_receipt()` retorna `"noop-ref-{event.gr_id[:8]}"`
- [ ] `pull_purchase_orders()` retorna `[]`
- [ ] `push_map_update()` retorna `None`
- [ ] `health_check()` retorna `True`

### SAPAdapter stub (`app/integrations/erp/sap_adapter.py`)
- [ ] Clase `SAPAdapter(ERPAdapter)` con docstring explicando:
      - Protocolo esperado: SAP RFC (BAPI_GOODSMVT_CREATE para GR, BAPI_PO_GET_LIST para pull POs)
      - Campos SAP → MT mapping documentado en comentarios inline
      - Configuración necesaria: `SAP_HOST`, `SAP_SYSTEM_NUMBER`, `SAP_CLIENT`, `SAP_USER`, `SAP_PASSWORD`
- [ ] Todos los métodos hacen `raise NotImplementedError("SAPAdapter: configure SAP RFC connection")`
- [ ] Variables `SAP_*` definidas en `app/core/config.py` con defaults vacíos

### OdooAdapter stub (`app/integrations/erp/odoo_adapter.py`)
- [ ] Clase `OdooAdapter(ERPAdapter)` con docstring explicando:
      - Protocolo: Odoo JSON-RPC (`/web/dataset/call_kw`)
      - Modelo Odoo: `stock.picking` para GR, `purchase.order` para POs
      - Configuración: `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`
- [ ] Todos los métodos hacen `raise NotImplementedError("OdooAdapter: configure Odoo JSON-RPC")`
- [ ] Variables `ODOO_*` en `app/core/config.py` con defaults vacíos

### Factory (`app/integrations/erp/factory.py`)
- [ ] `get_erp_adapter() -> ERPAdapter` singleton (instancia cacheada a nivel de módulo)
- [ ] Lee `settings.ERP_ADAPTER`: `"noop"` → `NoOpAdapter`, `"sap"` → `SAPAdapter`,
      `"odoo"` → `OdooAdapter`, otro valor → raise `ValueError`
- [ ] `ERP_DEBUG: bool = False` en `app/core/config.py`

### Health check endpoint
- [ ] `GET /api/v1/admin/erp/health` — requiere rol `admin`
      Retorna: `{adapter: "noop", healthy: true, checked_at: "..."}`
      Llama `await erp_adapter.health_check()`
      En caso de excepción: `{adapter: "sap", healthy: false, error: "..."}`

### Tests
- [ ] `tests/integrations/erp/test_noop_adapter.py`:
      - `test_push_goods_receipt_returns_ref`
      - `test_pull_purchase_orders_returns_empty`
      - `test_health_check_true`
      - `test_factory_returns_noop_by_default`
      - `test_factory_raises_on_unknown_adapter`

## Notas Técnicas

- El adapter es un singleton para evitar reconexiones innecesarias cuando se implementen
  los adapters reales (SAP/Odoo usan conexiones de larga duración)
- El `ERP_DEBUG` flag es importante durante la integración: permite ver el payload
  exacto que se enviaría al ERP sin contaminar los logs de producción
- Aunque los stubs SAP y Odoo tienen `NotImplementedError`, tener los campos documentados
  inline ahorra semanas de análisis cuando llegue el momento de la integración real
- Para SAP: la librería Python recomendada es `pyrfc` (wrapper de SAP NW RFC SDK).
  Para Odoo: `xmlrpc.client` (stdlib) o `odoorpc` (pip)
- No crear dependencias en `requirements.txt` para SAP/Odoo aún — solo cuando se implementen

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/integrations/erp/adapter.py` | Modificar (refinar ABC con tipado completo) |
| `app/integrations/erp/events.py` | Modificar (completar dataclasses) |
| `app/integrations/erp/noop_adapter.py` | Modificar (add logging, return values) |
| `app/integrations/erp/sap_adapter.py` | Modificar (add docstrings + mapping) |
| `app/integrations/erp/odoo_adapter.py` | Modificar (add docstrings + mapping) |
| `app/integrations/erp/factory.py` | Modificar (singleton + ERP_DEBUG) |
| `app/core/config.py` | Modificar (SAP_*, ODOO_*, ERP_DEBUG) |
| `app/api/routes/admin.py` | Modificar (agregar /erp/health) |
| `tests/integrations/erp/test_noop_adapter.py` | Crear |
| `tests/integrations/erp/__init__.py` | Crear |

## Tests / Validación

```bash
pytest tests/integrations/erp/ -v
# Expected: 5 tests pass

# Smoke:
# GET /api/v1/admin/erp/health → {adapter: "noop", healthy: true}
# ERP_ADAPTER=unknown → 500 con ValueError en startup (o al primer uso)
```
