# US-INV-01-01 — Modelo de datos: purchase_orders, goods_receipts, cost_lots, inventory_positions

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 1 | **SP**: 13 | **Prioridad**: P0 — BLOQUEANTE

## Contexto

Bloqueante para US-INV-01-02, 03, 04, 05, 06, 08.
El sistema actual tiene la tabla `costs` con una única fila activa por
`(sku, scheme_code, supplier_code)`. Esta story crea el modelo relacional completo
para soportar Purchase Orders → Goods Receipts → MAP automático, siguiendo el estándar
SAP MM / NetSuite para empresas distribuidoras.

Tablas anteriores (`costs`, `schemes`, `fx_rates`) **no se modifican** en esta story —
la integración con `costs` ocurre en US-INV-01-02 (MAP Engine).

## Descripción

Crear 5 tablas nuevas con sus modelos SQLAlchemy y migraciones Alembic.
Añadir la capa de integración ERP (`app/integrations/erp/`) con los stubs vacíos
del adapter pattern. No hay lógica de negocio en esta story — solo el schema.

## Criterios de Aceptación

### purchase_orders
- [ ] Tabla `purchase_orders` con columnas: `id UUID PK`, `po_number VARCHAR(64) UNIQUE NOT NULL`,
      `supplier_code VARCHAR(64) FK → suppliers.code ON DELETE RESTRICT`,
      `status VARCHAR(32) NOT NULL DEFAULT 'draft'`
      CHECK `status IN ('draft','confirmed','partial','received','cancelled')`,
      `currency VARCHAR(3) FK → currencies.code`, `notes TEXT`,
      `confirmed_at TIMESTAMP TZ`, `created_by UUID FK → users.id ON DELETE SET NULL`,
      `created_at`, `updated_at`
- [ ] Index `idx_po_supplier` on `(supplier_code, status)`
- [ ] Index `idx_po_status` partial: `WHERE status NOT IN ('received','cancelled')`

### purchase_order_lines
- [ ] Tabla `purchase_order_lines`: `id UUID PK`, `po_id UUID FK → purchase_orders.id ON DELETE CASCADE`,
      `sku TEXT FK → products.sku ON DELETE RESTRICT`,
      `scheme_code VARCHAR(32) FK → schemes.code ON DELETE RESTRICT`,
      `qty_ordered NUMERIC(12,3) NOT NULL`, CHECK `qty_ordered > 0`,
      `qty_received NUMERIC(12,3) NOT NULL DEFAULT 0`, CHECK `qty_received >= 0`,
      `unit_price NUMERIC(18,4) NOT NULL`, CHECK `unit_price >= 0`,
      `landed_cost_breakdown JSONB NOT NULL DEFAULT '{}'`,
      `created_at`, `updated_at`
- [ ] Index `idx_pol_po` on `po_id`
- [ ] Index `idx_pol_sku` on `sku`

### goods_receipts
- [ ] Tabla `goods_receipts`: `id UUID PK`,
      `po_line_id UUID FK → purchase_order_lines.id ON DELETE RESTRICT`,
      `qty_received NUMERIC(12,3) NOT NULL`, CHECK `qty_received > 0`,
      `received_at TIMESTAMP TZ NOT NULL DEFAULT now()`,
      `received_by UUID FK → users.id ON DELETE SET NULL`,
      `actual_unit_price NUMERIC(18,4)`,
      `actual_breakdown JSONB NOT NULL DEFAULT '{}'`,
      `map_before NUMERIC(18,4)`, `map_after NUMERIC(18,4)`,
      `fx_rate_id UUID FK → fx_rates.id ON DELETE SET NULL`,
      `notes TEXT`,
      `status VARCHAR(32) NOT NULL DEFAULT 'pending'`
      CHECK `status IN ('pending','processed','error')`,
      `processed_at TIMESTAMP TZ`,
      `created_at`, `updated_at`
- [ ] Index `idx_gr_po_line` on `po_line_id`
- [ ] Index `idx_gr_status_pending` partial: `WHERE status = 'pending'`
- [ ] Index `idx_gr_received_at` on `received_at DESC`

### cost_lots
- [ ] Tabla `cost_lots`: `id UUID PK`,
      `sku TEXT FK → products.sku ON DELETE RESTRICT`,
      `supplier_code VARCHAR(64) NOT NULL`,
      `scheme_code VARCHAR(32) FK → schemes.code ON DELETE RESTRICT`,
      `gr_id UUID FK → goods_receipts.id ON DELETE RESTRICT`,
      `qty_original NUMERIC(12,3) NOT NULL`, CHECK `qty_original > 0`,
      `qty_remaining NUMERIC(12,3) NOT NULL`, CHECK `qty_remaining >= 0`,
      `unit_cost_aed NUMERIC(18,4) NOT NULL`, CHECK `unit_cost_aed >= 0`,
      `effective_at TIMESTAMP TZ NOT NULL DEFAULT now()`,
      `created_at`, `updated_at`
- [ ] Index `idx_cost_lots_lookup` on `(sku, supplier_code, scheme_code)`
- [ ] Index `idx_cost_lots_gr` on `gr_id`
- [ ] CHECK constraint `qty_remaining <= qty_original`

### inventory_positions
- [ ] Tabla `inventory_positions`: `id UUID PK`,
      `sku TEXT FK → products.sku ON DELETE RESTRICT`,
      `supplier_code VARCHAR(64) NOT NULL`,
      `scheme_code VARCHAR(32) FK → schemes.code ON DELETE RESTRICT`,
      `qty_on_hand NUMERIC(12,3) NOT NULL DEFAULT 0`,
      `map_aed NUMERIC(18,4)` (NULL si aún sin recepción),
      `total_stock_value_aed NUMERIC(18,4)` (computed: `qty_on_hand * map_aed`),
      `last_gr_id UUID FK → goods_receipts.id ON DELETE SET NULL`,
      `last_updated_at TIMESTAMP TZ`,
      `created_at`, `updated_at`
- [ ] UNIQUE constraint `uq_inventory_positions` on `(sku, supplier_code, scheme_code)`
- [ ] Index `idx_inv_pos_sku` on `sku`

### Modelos SQLAlchemy
- [ ] `app/db/models/inventory.py` con clases `PurchaseOrder`, `PurchaseOrderLine`,
      `GoodsReceipt`, `CostLot`, `InventoryPosition` usando `UuidPkMixin`, `TimestampMixin`
- [ ] Exports en `app/db/models/__init__.py`
- [ ] Enums en `app/db/enums.py`: `POStatus`, `GRStatus`

### ERP Adapter Layer (stubs — sin lógica)
- [ ] Directorio `app/integrations/erp/` con `__init__.py`
- [ ] `app/integrations/erp/adapter.py`: clase abstracta `ERPAdapter` con métodos:
      `push_goods_receipt`, `pull_purchase_orders`, `push_map_update`, `health_check`
- [ ] `app/integrations/erp/noop_adapter.py`: `NoOpAdapter` que implementa todos los
      métodos retornando valores vacíos (no lanza excepciones)
- [ ] `app/integrations/erp/sap_adapter.py`: stub con `raise NotImplementedError`
- [ ] `app/integrations/erp/odoo_adapter.py`: stub con `raise NotImplementedError`
- [ ] `app/integrations/erp/factory.py`: `get_erp_adapter()` que lee `settings.ERP_ADAPTER`
      (`"noop"` por defecto) y devuelve la instancia correcta
- [ ] `app/integrations/erp/events.py`: dataclasses `GoodsReceivedEvent`, `MAPUpdatedEvent`,
      `POImport` (campo `po_number`, `lines: list[POLineImport]`)
- [ ] Variable `ERP_ADAPTER: str = "noop"` en `app/core/config.py`
- [ ] Variable `ERP_WEBHOOK_SECRET: str = ""` en `app/core/config.py` (para HMAC — US-INV-01-07)

### Migración Alembic
- [ ] Migración `20260512_090_inv_purchase_orders.py` — tabla `purchase_orders`
- [ ] Migración `20260512_091_inv_po_lines.py` — tabla `purchase_order_lines`
- [ ] Migración `20260512_092_inv_goods_receipts.py` — tabla `goods_receipts`
- [ ] Migración `20260512_093_inv_cost_lots.py` — tabla `cost_lots`
- [ ] Migración `20260512_094_inv_inventory_positions.py` — tabla `inventory_positions`
- [ ] `alembic upgrade head` ejecuta sin errores en DB local limpia

## Notas Técnicas

- Usar `UuidPkMixin` y `TimestampMixin` del proyecto (ya en `app/db/mixins.py`)
- `landed_cost_breakdown` y `actual_breakdown` siguen el mismo convenio de sufijos
  que `costs.breakdown` (`*_aed` directo, `*_eur` convertido, `*_pct` porcentual)
- `total_stock_value_aed` se puede expresar como generated column de Postgres o
  calcularse al escribir desde el MAP Engine — preferir generated column:
  `GENERATED ALWAYS AS (qty_on_hand * map_aed) STORED`
- No hay triggers en esta story — el MAP Engine (US-INV-01-02) se encarga de las writes

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/db/models/inventory.py` | Crear (5 modelos) |
| `app/db/models/__init__.py` | Modificar (exports) |
| `app/db/enums.py` | Modificar (POStatus, GRStatus) |
| `app/integrations/__init__.py` | Crear (vacío) |
| `app/integrations/erp/__init__.py` | Crear (vacío) |
| `app/integrations/erp/adapter.py` | Crear (ABC) |
| `app/integrations/erp/noop_adapter.py` | Crear |
| `app/integrations/erp/sap_adapter.py` | Crear (stub) |
| `app/integrations/erp/odoo_adapter.py` | Crear (stub) |
| `app/integrations/erp/factory.py` | Crear |
| `app/integrations/erp/events.py` | Crear (dataclasses) |
| `app/core/config.py` | Modificar (ERP_ADAPTER, ERP_WEBHOOK_SECRET) |
| `alembic/versions/20260512_090_*.py` | Crear |
| `alembic/versions/20260512_091_*.py` | Crear |
| `alembic/versions/20260512_092_*.py` | Crear |
| `alembic/versions/20260512_093_*.py` | Crear |
| `alembic/versions/20260512_094_*.py` | Crear |

## Tests / Validación

- `alembic upgrade head && alembic downgrade -5 && alembic upgrade head` — sin errores
- `pytest tests/db/test_inventory_models.py` — CRUD básico para cada modelo
- `from app.integrations.erp.factory import get_erp_adapter; a = get_erp_adapter()` — instancia NoOpAdapter
- `await a.health_check()` → `True` sin excepciones
