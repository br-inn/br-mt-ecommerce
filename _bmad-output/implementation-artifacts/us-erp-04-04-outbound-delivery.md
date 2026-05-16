# Story Artifact: US-ERP-04-04 — Outbound Delivery entity + Goods Issue

**Epic:** EP-ERP-04 — Ventas O2C  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Entidad `outbound_deliveries` separada del SO, con lifecycle picking/packing/goods_issued.
Al confirmar Goods Issue: reducción de inventario (stock_movement GI) y creación automática
de AR open item.

## Implementación verificada

### Migración
- `20260524_113_outbound_delivery.py` — crea tablas:
  - `outbound_deliveries` (so_id, warehouse_id, status, partial_delivery_allowed, shipped_at)
    - Unique: `delivery_number`
    - CHECK: `status IN ('pending_pick','picking','packed','goods_issued','cancelled')`
    - FK → `sales_orders`, `warehouses`
  - `outbound_delivery_lines` (delivery_id, so_line_id, product_sku, qty_planned, qty_picked, qty_packed)

### Modelos (`app/db/models/sales.py`)
- `OutboundDelivery` — `__tablename__ = "outbound_deliveries"`
- `OutboundDeliveryLine` — `__tablename__ = "outbound_delivery_lines"`

### API (`app/api/routes/sales.py`)
- `GET /api/v1/sales/deliveries` — listar entregas
- `POST /api/v1/sales/deliveries` — crear entrega desde SO
- `PATCH /api/v1/sales/deliveries/{id}/status` — actualizar estado picking→packed
- `POST /api/v1/sales/deliveries/{id}/goods-issue` — confirmar GI → stock_movement GI + AR open item

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `outbound_deliveries` con lifecycle correcto | ✅ migración + modelo |
| Status: pending_pick → picking → packed → goods_issued | ✅ CHECK constraint |
| Al Goods Issue: stock_movement de tipo GI reduce inventario | ✅ endpoint `goods-issue` |
| Al Goods Issue: crear AR open item | ✅ lógica en goods_issue handler |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260524_113_outbound_delivery.py`
- `mt-pricing-backend/app/db/models/sales.py` (OutboundDelivery, OutboundDeliveryLine)
- `mt-pricing-backend/app/api/routes/sales.py` (list_deliveries, create_delivery, update_delivery_status, goods_issue)
