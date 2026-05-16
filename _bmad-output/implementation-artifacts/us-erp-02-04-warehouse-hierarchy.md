---
story_key: US-ERP-02-04
title: Jerarquia almacen — Warehouse → Zone → Location (bin)
status: review
sprint: S14
story_points: 5
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/erp-02-inv, 4ac94e8).

**Migraciones:**
- `20260515_108_warehouses_zones_locations.py` — tablas `warehouses`, `warehouse_zones` (tipos: refrigerado/seco/peligroso/general), `warehouse_locations` (bin con codigo estructurado). FK `inventory_positions.location_id` → `warehouse_locations`.

**Modelos:** `app/db/models/inventory.py` — clases `Warehouse`, `WarehouseZone`, `WarehouseLocation` con jerarquia completa.

**Rutas:** `app/api/routes/warehouses.py` (registrada en `__init__.py`):
- `GET /warehouses` — listar almacenes
- `POST /warehouses` — crear almacen
- `GET /warehouses/{id}/zones` — listar zonas
- `POST /warehouses/{id}/zones` — crear zona
- `GET /warehouses/{id}/zones/{zone_id}/locations` — listar ubicaciones (bins)
- `POST /warehouses/{id}/zones/{zone_id}/locations` — crear ubicacion

**Filtros en positions dashboard:** `GET /inventory/positions` acepta `warehouse_id` y `zone_id`.

## ACs verificados

- ✅ Tablas: `warehouses`, `warehouse_zones` (refrigerado, seco, peligroso, general), `warehouse_locations` (bin con codigo estructurado)
- ✅ Codigo de bin: `{warehouse_code}-{zone}-{fila}-{nivel}-{posicion}` (ej: `WH1-A-03-02-B`)
- ✅ `inventory_positions.location_id` → FK a `warehouse_locations`
- ✅ CRUD admin: `GET/POST/PATCH /api/v1/warehouses` y sub-recursos
- ✅ Filtros en positions dashboard por warehouse y zone
