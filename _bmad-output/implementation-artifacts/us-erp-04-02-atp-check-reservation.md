---
story_key: US-ERP-04-02
title: ATP check en SO + soft reservation de stock
status: review
sprint: S14
story_points: 13
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/o2c, 25c66bd).

**Migraciones:**
- `20260524_111_atp_reservations.py` — tabla `atp_checking_rules` (configurable por producto: incluir/excluir safety stock, GRs planeados, stock en QA). Tabla `stock_reservations` (so_line_id, product_id, warehouse_id, qty, expiry).

**Modelos:** `app/db/models/sales.py` — clases `AtpCheckingRule`, `StockReservation`.

**Rutas:** `app/api/routes/sales.py`:
- `POST /sales/orders/{id}/atp-check` — calcula ATP Qty = stock_unrestricted + GRs_planeados - reservas_activas. Si ATP >= qty: confirma fecha; si no: propone `first_available_date`.
- `POST /sales/orders/{id}/confirm` — al confirmar: crea `stock_reservations` reduciendo ATP disponible para nuevos pedidos.

**Worker Celery:** al procesar GR: re-evalua backorders y actualiza fechas de entrega prometidas.

## ACs verificados

- ✅ `POST /api/v1/sales/orders/{id}/atp-check`: calcula `ATP Qty = stock_unrestricted + GRs_planeados − reservas_activas`
- ✅ Si `ATP Qty >= qty_requested`: confirmar fecha; si no: proponer `first_available_date`
- ✅ `checking_rules` configurable por producto: incluir/excluir safety stock, GRs planeados, stock en QA
- ✅ Al confirmar linea de SO: crear `stock_reservations` (so_line_id, product_id, warehouse_id, qty, expiry)
- ✅ Las reservas reducen el ATP disponible para nuevos pedidos
- ✅ Job Celery al procesar GR: re-evaluar backorders y actualizar fechas
