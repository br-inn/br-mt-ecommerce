---
stepsCompleted: [prd, architecture, epics-stories]
inputDocuments:
  - best-practices-erp-inventory-costing
  - existing-cost-model-analysis
  - map-design-session-2026-05-12
generated: "2026-05-12T00:00:00.000Z"
project: "MT Middle East MDM + Pricing — EP-INV-01 Inventory Costing & Purchase Orders"
---

# EP-INV-01 — Inventory Costing: Purchase Orders, Goods Receipts & MAP Engine

## Contexto y motivación

El sistema actual gestiona costes con una única fila activa por `(sku, scheme_code, supplier_code)`.
Cuando un artículo se compra en múltiples órdenes con precios distintos (precio FOB + aranceles
variables por negociación), el sistema no tiene mecanismo para actualizar el coste de forma
automática ni para calcular el Coste Medio Ponderado (MAP/WAC — estándar IFRS IAS-2).

Esta épica implementa el modelo robusto y escalable que sigue SAP Business One, NetSuite y
Odoo 17 para empresas distribuidoras:

```
Pedido de Compra (PO) → Recepción de Mercancía (GR) → MAP Engine (Celery)
                                                              ↓
                                                   inventory_positions (MAP actual)
                                                              ↓
                                                   costs (actualizado — pricing engine sin cambios)
```

**Preparación ERP**: la arquitectura usa el patrón Ports & Adapters para la capa de integración.
Por defecto opera `NoOpAdapter`. Cuando el cliente conecte SAP/Oracle/Odoo, se enchufará un
adapter concreto sin cambios en el dominio.

## Requerimientos funcionales cubiertos

| FR | Descripción |
|----|-------------|
| FR-INV-001 | Gestión de Pedidos de Compra (PO) con líneas por SKU |
| FR-INV-002 | Registro de Recepciones de Mercancía (GR) con cantidades reales |
| FR-INV-003 | Cálculo automático de MAP en cada recepción |
| FR-INV-004 | Capas de inventario (cost_lots) para soporte futuro FIFO |
| FR-INV-005 | Posiciones de inventario agregadas por (sku, scheme, supplier) |
| FR-INV-006 | Recálculo de precios automático post-MAP (Celery fan-out existente) |
| FR-INV-007 | ERP adapter layer — NoOp por defecto, enchufable sin cambios de dominio |
| FR-INV-008 | Event log de sincronización ERP con reintentos y HMAC |
| FR-INV-009 | Dashboard de posiciones de inventario con historial MAP |
| FR-INV-010 | Migración backwards-compat: costes existentes → inventory_positions seed |

## Requerimientos no funcionales

| NFR | Descripción |
|-----|-------------|
| NFR-INV-001 | MAP calculado en < 2s vía Celery (async, no bloquea el API) |
| NFR-INV-002 | Backwards compat total: `/api/v1/costs/*` sigue funcionando sin cambios |
| NFR-INV-003 | Audit trail completo: cada cambio de MAP vinculado al GR que lo originó |
| NFR-INV-004 | Idempotencia: doble procesamiento del mismo GR no corrompe el MAP |
| NFR-INV-005 | ERP adapter falla silenciosamente (circuit breaker) — no bloquea el dominio |

## Épica EP-INV-01 — Resumen de stories

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-INV-01-01 | Modelo de datos: POs, GRs, cost_lots, inventory_positions | 13 | P0 | S12 W1 |
| US-INV-01-02 | MAP Engine — cálculo automático en Goods Receipt | 8 | P0 | S12 W2 |
| US-INV-01-03 | Purchase Orders CRUD + UI | 8 | P1 | S12 W2 |
| US-INV-01-04 | Goods Receipts registro + UI | 8 | P0 | S12 W2 |
| US-INV-01-05 | Inventory Positions dashboard | 5 | P1 | S12 W3 |
| US-INV-01-06 | ERP Integration Adapter Layer (NoOp por defecto) | 8 | P1 | S12 W3 |
| US-INV-01-07 | ERP Webhooks outbound + event log | 5 | P2 | S12 W4 |
| US-INV-01-08 | Migración backwards-compat + seed inventory_positions | 3 | P0 | S12 W1 |

**Total: 58 SP**

## Modelo de datos — visión completa

### Nuevas tablas

```sql
-- Pedidos de compra
purchase_orders
  id UUID PK
  po_number VARCHAR(64) UNIQUE
  supplier_code VARCHAR(64) FK → suppliers.code
  status VARCHAR(32)  -- draft | confirmed | partial | received | cancelled
  currency VARCHAR(3) FK → currencies.code
  notes TEXT
  confirmed_at TIMESTAMP TZ
  created_by UUID FK → users.id
  [timestamps, audit]

-- Líneas de pedido
purchase_order_lines
  id UUID PK
  po_id UUID FK → purchase_orders.id ON DELETE CASCADE
  sku TEXT FK → products.sku
  scheme_code VARCHAR(32) FK → schemes.code
  qty_ordered NUMERIC(12,3)
  qty_received NUMERIC(12,3) DEFAULT 0
  unit_price NUMERIC(18,4)          -- en moneda del PO
  landed_cost_breakdown JSONB       -- mismo convenio de sufijos que costs.breakdown
  [timestamps]

-- Recepciones de mercancía
goods_receipts
  id UUID PK
  po_line_id UUID FK → purchase_order_lines.id
  qty_received NUMERIC(12,3)
  received_at TIMESTAMP TZ
  received_by UUID FK → users.id
  actual_unit_price NUMERIC(18,4)   -- puede diferir del PO (precio real factura)
  actual_breakdown JSONB            -- coste real con aranceles definitivos
  map_before NUMERIC(18,4)          -- MAP antes de esta recepción
  map_after NUMERIC(18,4)           -- MAP después (calculado por MAP Engine)
  fx_rate_id UUID FK → fx_rates.id
  notes TEXT
  status VARCHAR(32) DEFAULT 'pending'  -- pending | processed | error
  processed_at TIMESTAMP TZ
  [timestamps]

-- Capas de inventario (soporte FIFO futuro)
cost_lots
  id UUID PK
  sku TEXT FK → products.sku
  supplier_code VARCHAR(64)
  scheme_code VARCHAR(32) FK → schemes.code
  gr_id UUID FK → goods_receipts.id
  qty_original NUMERIC(12,3)
  qty_remaining NUMERIC(12,3)       -- decrementado por ventas (Fase 2)
  unit_cost_aed NUMERIC(18,4)       -- coste aterrizaje AED de este lote
  effective_at TIMESTAMP TZ
  [timestamps]

-- Posiciones de inventario (estado MAP agregado)
inventory_positions
  id UUID PK
  sku TEXT FK → products.sku
  supplier_code VARCHAR(64)
  scheme_code VARCHAR(32) FK → schemes.code
  qty_on_hand NUMERIC(12,3) DEFAULT 0
  map_aed NUMERIC(18,4)             -- MAP actual en AED
  total_stock_value_aed NUMERIC(18,4)  -- qty_on_hand × map_aed
  last_gr_id UUID FK → goods_receipts.id
  last_updated_at TIMESTAMP TZ
  [timestamps]
  UNIQUE (sku, supplier_code, scheme_code)
```

### Relación con tabla `costs` existente

El MAP Engine, después de calcular el nuevo `map_aed`, llama a `CostService.update_cost()`
con el breakdown reconstruido desde el GR. Esto:
1. Crea nueva versión del `Cost` (version + 1)
2. Marca el anterior como `superseded`
3. El pricing engine continúa leyendo `costs.scheme_landed_aed` **sin ningún cambio**

### ERP Adapter Layer

```
app/integrations/erp/
  __init__.py
  adapter.py          # Abstract ERPAdapter (Puerto)
  noop_adapter.py     # NoOpAdapter — default, no hace nada
  sap_adapter.py      # SAPAdapter — stub listo para implementar
  odoo_adapter.py     # OdooAdapter — stub listo para implementar
  factory.py          # get_erp_adapter() desde config ERP_ADAPTER=noop|sap|odoo
  events.py           # ERPEvent dataclasses: GoodsReceivedEvent, MAPUpdatedEvent, etc.
```

```python
class ERPAdapter(ABC):
    @abstractmethod
    async def push_goods_receipt(self, event: GoodsReceivedEvent) -> str: ...
    @abstractmethod
    async def pull_purchase_orders(self, since: datetime) -> list[POImport]: ...
    @abstractmethod
    async def push_map_update(self, event: MAPUpdatedEvent) -> None: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
```

## Flujo end-to-end post-épica

```
1. Usuario crea PO en /compras/pedidos (POST /api/v1/purchase-orders)
2. Mercancía llega → Usuario registra GR en /compras/recepciones
   (POST /api/v1/goods-receipts)
3. Celery task recalc_map_on_gr.delay(gr_id):
   a. Lee cost_lots existentes para (sku, scheme, supplier)
   b. Calcula nuevo MAP = (stock_value + new_lot_value) / (qty_old + qty_new)
   c. Escribe inventory_positions.map_aed
   d. Escribe cost_lots (nueva capa)
   e. Llama CostService.update_cost() → costs table actualizada
   f. Dispara recalc_prices_by_sku.delay(sku) — existente en la arquitectura
   g. Llama erp_adapter.push_goods_receipt() vía Celery task separado
4. Pricing engine en siguiente ciclo usa costs.scheme_landed_aed actualizado
5. Precios re-propuestos pasan por workflow aprobación normal
```
