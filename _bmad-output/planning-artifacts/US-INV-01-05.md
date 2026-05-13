# US-INV-01-05 — Inventory Positions Dashboard

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 3 | **SP**: 5 | **Prioridad**: P1

## Contexto

Depende de US-INV-01-02 (MAP Engine) y US-INV-01-04 (GRs).
Provee visibilidad del estado actual del inventario valorado y el historial del MAP
por SKU. Es la pantalla de control equivalente al informe MB52/MB5B de SAP
(stock valorado + historial de movimientos).

## Descripción

Implementar API de consulta de `inventory_positions` y la pantalla frontend
`/inventario` con vista de posiciones actuales y detalle por SKU con historial de MAP.

## Criterios de Aceptación

### API
- [ ] `GET /api/v1/inventory/positions` — lista todas las posiciones activas
      Filtros: `?sku=&supplier_code=&scheme_code=&has_stock=true`
      Respuesta: `{items: [InventoryPositionRead], total: int}`
      Incluye: `sku`, `supplier_code`, `scheme_code`, `qty_on_hand`, `map_aed`,
      `total_stock_value_aed`, `last_updated_at`, `last_gr_id`
- [ ] `GET /api/v1/inventory/positions/{sku}` — posición por SKU (todas las combinaciones
      scheme × supplier para ese SKU)
- [ ] `GET /api/v1/inventory/positions/{sku}/map-history` — historial de cambios MAP
      para el SKU (lista de `{gr_id, map_before, map_after, qty_received, received_at}`)
      desde `goods_receipts WHERE sku = X AND status = 'processed'` join `po_lines`
      ordenado por `received_at DESC`, límite 50
- [ ] `GET /api/v1/inventory/summary` — agregado:
      `{total_skus_with_stock: int, total_stock_value_aed: Decimal, skus_without_cost: int}`
      (para widget en el dashboard principal)

### Frontend — `/inventario`
- [ ] Página con 2 tabs: "Posiciones" y "Resumen"

**Tab Posiciones:**
- [ ] Tabla con columnas: `SKU`, `Descripción producto`, `Proveedor`, `Scheme`,
      `Qty en stock`, `MAP (AED)`, `Valor stock (AED)`, `Última recepción`
- [ ] Fila sin posición o `qty_on_hand = 0`: fondo gris claro (sin stock)
- [ ] Fila con `map_aed = null`: badge "Sin coste" en rojo (nunca tuvo GR)
- [ ] Click en SKU → drawer lateral con historial MAP (gráfico + tabla)
- [ ] Filtro: `?scheme_code=FBA|FBM|...` (selector de scheme)

**Drawer "Historial MAP" (SKU seleccionado):**
- [ ] Gráfico de línea: eje X = fecha recepción, eje Y = MAP AED
      (usar Recharts que ya está en el proyecto)
- [ ] Tabla debajo del gráfico: columnas `Fecha`, `Qty recibida`, `MAP antes`, `MAP después`,
      `Δ MAP`, `PO#` (link a `/compras/pedidos/{po_id}`)
- [ ] Badge color en Δ MAP: verde si bajó, rojo si subió, gris si sin cambio

**Tab Resumen (KPIs):**
- [ ] Card: Total SKUs con stock / Total SKUs en catálogo
- [ ] Card: Valor total inventario AED (Σ total_stock_value_aed)
- [ ] Card: SKUs sin coste registrado (qty_on_hand > 0 pero map_aed null)
- [ ] Card: Recepciones pendientes (GRs con status='pending' > 5 min)

### Navegación
- [ ] Ítem "Inventario" en el sidebar (sección Compras o sección propia)
- [ ] Widget de resumen en `/dashboard` principal: 3 KPIs de inventario con link a `/inventario`

## Notas Técnicas

- `GET /api/v1/inventory/summary` puede ser una view materializada o una query agregada
  — con 224 SKUs, una query directa es suficiente (sin caché por ahora)
- El gráfico de línea del historial MAP: si hay muchos puntos, limitar a últimos 12 meses
  o últimas 20 recepciones (la mayoría de SKUs tendrá < 20 GRs en el año)
- Los "SKUs sin coste" del tab resumen son los que tienen stock en inventario
  pero `map_aed IS NULL` — condición de error que el operador debe resolver

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/api/routes/inventory.py` | Crear |
| `app/api/router.py` | Modificar |
| `app/schemas/inventory.py` | Crear |
| `app/repositories/inventory.py` | Crear |
| `mt-pricing-frontend/app/(app)/inventario/page.tsx` | Crear |
| `mt-pricing-frontend/lib/api/endpoints/inventory.ts` | Crear |
| `mt-pricing-frontend/components/inventario/map-history-drawer.tsx` | Crear |
| `mt-pricing-frontend/app/(app)/dashboard/page.tsx` | Modificar (widget KPIs) |
| `mt-pricing-frontend/components/layout/sidebar.tsx` | Modificar |

## Tests / Validación

```bash
pytest tests/api/test_inventory.py -v
# Tests: list positions, map history, summary counts

# Smoke UI:
# 1. Ir a /inventario — muestra SKUs con posiciones creadas en US-INV-01-04
# 2. Click en SKU → drawer con historial MAP (al menos 1 punto)
# 3. Tab Resumen → KPIs con valores reales
# 4. Dashboard principal → widget inventario visible
```
