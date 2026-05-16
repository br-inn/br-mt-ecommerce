# US-ERP-02-01 — Movement Types catalog + stock_movements

**Status:** review
**Sprint:** S13
**Story Points:** 8
**Epic:** EP-ERP-02 — Inventario v2
**Fecha implementación:** 2026-05-16

## Resumen

Implementación del catálogo de tipos de movimiento SAP-MM y el registro de movimientos físicos de stock con asientos contables vinculados.

## Componentes implementados

### Migración
- `mt-pricing-backend/alembic/versions/20260515_105_stock_movement_types_and_movements.py`
  - Tablas: `stock_movement_types`, `stock_movements`, `journal_entries`
  - Seed: 6 tipos SAP-MM (101 GR vs PO, 102 Reversal, 261 GI vs SO, 301 Transfer, 551 Scrap, 561 Opening Balance)
  - `down_revision` corregido a `"20260513_104"` (migración base ERP branches)

### Migración base creada
- `mt-pricing-backend/alembic/versions/20260513_104_fts_gin_fix.py` — ya existía como punto de bifurcación

### Modelos
- `mt-pricing-backend/app/db/models/inventory.py` — `StockMovementType`, `StockMovement`, `JournalEntry`

### Repositorio
- `mt-pricing-backend/app/repositories/inventory.py` — `InventoryRepository` con `list_movement_types()`, `list_movements()`, `create_movement()`

### Endpoints (prefijo `/api/v1/inventory`)
- `GET /inventory/movement-types` — catálogo SAP-MM
- `GET /inventory/movements` — lista con filtros limit
- `POST /inventory/movements` — registrar movimiento
- `POST /inventory/movements/{id}/reverse` — reversión

## Verificación

- Alembic: `20260531_133 (head)` — DB al día, sin migraciones pendientes
- Endpoints responden 401 (auth requerida) — registrados correctamente
- Tests unitarios: 883 passed (fallos pre-existentes en matching/scraping, no relacionados)
