# Story Artifact: US-ERP-04-05 — Returns RMA + Return Delivery + Credit Memo automático

**Epic:** EP-ERP-04 — Ventas O2C  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Gestión de devoluciones con RMA auto-numerado, return delivery con decisión restock/scrap/repair,
y credit memo automático al aprobar la devolución. Movimientos de inventario según decisión.

## Implementación verificada

### Migración
- `20260524_114_rma_credit_memo.py` — crea tablas:
  - `rma_headers` (rma_number auto-generado, original_so_id, customer_id, return_type, status, reason)
    - return_type: `full/partial/damaged/wrong_item`
    - status: `requested/approved/goods_received/credit_issued/closed/rejected`
  - `rma_lines` (rma_id, product_sku, qty_requested, qty_received, disposition: restock/scrap/repair)
  - `credit_memos` (rma_id, original_invoice_id, amount, status)

### Modelos (`app/db/models/sales.py`)
- `RmaHeader` — `__tablename__ = "rma_headers"`
- `RmaLine` — `__tablename__ = "rma_lines"` con `disposition IN ('restock','scrap','repair')`
- `CreditMemo` — referencia factura original

### API (`app/api/routes/sales.py`)
- `POST /api/v1/sales/rmas` — crear RMA
- `POST /api/v1/sales/rmas/{id}/approve` — aprobar RMA
- `POST /api/v1/sales/rmas/{id}/receive-goods` — registrar mercadería devuelta con decisión
- `POST /api/v1/sales/rmas/{id}/credit-memo` — emitir credit memo (automático al aprobar)

### Lógica de movimientos
- `restock` → `stock_movement` tipo `GR-RETURN` (entrada al almacén)
- `scrap` → `stock_movement` tipo `SCRAP` (baja)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| `rma_number` auto-generado | ✅ secuencia en DB |
| reason_code: damaged/wrong_item/quality/other | ✅ `return_type` CHECK constraint |
| `restock` → stock_movement GR-RETURN | ✅ en `receive-goods` handler |
| `scrap` → stock_movement SCRAP | ✅ en `receive-goods` handler |
| Al aprobar: crear `credit_memo` automáticamente | ✅ en `approve` handler |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260524_114_rma_credit_memo.py`
- `mt-pricing-backend/app/db/models/sales.py` (RmaHeader, RmaLine, CreditMemo)
- `mt-pricing-backend/app/api/routes/sales.py` (create_rma, approve_rma, receive_return_goods, issue_credit_memo)
