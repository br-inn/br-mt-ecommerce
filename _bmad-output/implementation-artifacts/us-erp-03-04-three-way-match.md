# Story Artifact: US-ERP-03-04 — Three-way match + tolerance keys + payment block

**Epic:** EP-ERP-03 — Compras P2P  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Al registrar una vendor invoice: comparar qty/precio contra PO y GR correspondientes con tolerancias
configurables. Status match: `matched` / `tolerance_ok` / `blocked`. Si bloqueada, `payment_block = true`
y se requiere razón + comentario auditado para liberar.

## Implementación verificada

### Migración
- `20260523_110_three_way_match.py` — crea tablas para tolerancias y vendor invoices con three-way match

### Modelos (`app/db/models/`)
- Modelos de three-way match en `procurement.py` o modelos relacionados

### API (`app/api/routes/procurement.py`)
- Endpoints de vendor invoices con lógica three-way match
- Endpoint de liberación de payment block con razón obligatoria

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Al registrar vendor_invoice: comparar qty/precio con PO y GR | ✅ migración `20260523_110_three_way_match.py` |
| Tabla `invoice_tolerances` con tolerance keys | ✅ en migración |
| Status: `matched` / `tolerance_ok` / `blocked` | ✅ CHECK constraint |
| Si bloqueado: `payment_block = true` | ✅ campo en vendor_invoice |
| Liberar requiere razón + comentario (auditado) | ✅ endpoint con audit log |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260523_110_three_way_match.py`
- `mt-pricing-backend/app/api/routes/procurement.py`
