---
story_key: US-ERP-04-01
title: SO types + document chain reference completa
status: review
sprint: S14
story_points: 5
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/o2c, 25c66bd).

**Migraciones:**
- `20260524_110_sales_orders_chain.py` — campo `order_type` en `sales_orders` (STANDARD/RUSH/CASH/CONTRACT_RELEASE/RETURN). FK `quotation_id` en SO. FK `so_id` en `outbound_deliveries`, FK `delivery_id` en `invoices`.

**Modelo:** `app/db/models/sales.py` — clase `SalesOrder` con `order_type` enum. Clases `OutboundDelivery`, `CreditMemo` con FKs de cadena.

**Rutas:** `app/api/routes/sales.py`:
- `GET /sales/orders` — listar SOs
- `POST /sales/orders` — crear SO (con order_type)
- `GET /sales/orders/{id}` — detalle SO
- `PATCH /sales/orders/{id}` — actualizar SO
- `GET /sales/orders/{id}/chain` — cadena documental completa Quotation→SO→Delivery→Invoice

## ACs verificados

- ✅ Campo `order_type` en `sales_orders`: `STANDARD` / `RUSH` / `CASH` / `CONTRACT_RELEASE` / `RETURN`
- ✅ FK `quotation_id` en SO (opcional — si viene de una cotizacion)
- ✅ FK `so_id` en `outbound_deliveries`, FK `delivery_id` en `invoices`
- ✅ Endpoint de cadena: `GET /api/v1/sales/orders/{id}/chain` retorna Quotation→SO→Delivery→Invoice en un objeto
