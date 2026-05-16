---
story_key: US-ERP-03-03
title: PO types + Purchasing Info Record (PIR)
status: review
sprint: S14
story_points: 5
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/erp-03-p2p, a36abf9 / merge 0727e56).

**Migraciones:**
- `20260516_107_po_types_pir.py` — campo `po_type` en `purchase_orders` (STANDARD/BLANKET/CONTRACT/SCHEDULING). Tabla `vendor_product_conditions` (Purchasing Info Record) con vendor_id, product_id, price, uom, moq, lead_time_days, valid_from, valid_to.

**Modelo:** `app/db/models/procurement.py` — clase `VendorProductCondition` (PIR). Enum `po_type` en `PurchaseOrder`.

**Rutas:** `app/api/routes/procurement.py`:
- `GET /procurement/vendor-conditions` — listar PIRs vigentes (filtros vendor_id, product_id)
- `POST /procurement/vendor-conditions` — crear PIR
- `PUT /procurement/vendor-conditions/{id}` — actualizar PIR

**Logica:** Al crear linea de PO: si existe PIR vigente → pre-llenar precio automaticamente. Campo `price_source` indica si precio viene de PIR o es manual.

## ACs verificados

- ✅ Campo `po_type` en `purchase_orders`: `STANDARD` / `BLANKET` / `CONTRACT` / `SCHEDULING`
- ✅ Tabla `vendor_product_conditions` (Purchasing Info Record): vendor_id, product_id, price, uom, moq, lead_time_days, valid_from, valid_to
- ✅ Al crear linea de PO: si existe PIR vigente → pre-llenar precio automaticamente
- ✅ CRUD: `GET/POST/PUT /api/v1/procurement/vendor-conditions`
