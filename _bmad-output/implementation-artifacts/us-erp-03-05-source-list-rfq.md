# Story Artifact: US-ERP-03-05 — Source List + RFQ básico

**Epic:** EP-ERP-03 — Compras P2P  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Source List de proveedores aprobados por producto. Tablas `rfqs` + `rfq_lines` + `vendor_quotations`.
Endpoint de comparativa que muestra precios de proveedores ordenados. Si `mandatory=true`: bloquear POs
a vendedores fuera de la lista.

## Implementación verificada

### Migración
- `20260523_111_source_list_rfq.py` — crea tablas:
  - `product_approved_vendors` (Source List): product_id, vendor_id, is_preferred, is_blocked, valid_from/to
  - `rfqs`, `rfq_lines`, `vendor_quotations`

### API (`app/api/routes/procurement.py`)
- Source List CRUD
- RFQ creation y comparativa: `GET /api/v1/procurement/rfqs/{id}/comparison`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `product_approved_vendors` (Source List) con todos los campos | ✅ migración `20260523_111_source_list_rfq.py` |
| Bloquear POs a vendedores fuera de lista si `mandatory=true` | ✅ lógica en PO creation |
| Tablas `rfqs` + `rfq_lines` + `vendor_quotations` | ✅ en migración |
| Endpoint comparativa por proveedor ordenado por precio | ✅ `/procurement/rfqs/{id}/comparison` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260523_111_source_list_rfq.py`
- `mt-pricing-backend/app/api/routes/procurement.py`
