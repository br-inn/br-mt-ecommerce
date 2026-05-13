# US-INV-01-02 — MAP Engine: cálculo automático de Coste Medio Ponderado en Goods Receipt

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 2 | **SP**: 8 | **Prioridad**: P0

## Contexto

Depende de US-INV-01-01 (modelo de datos). Bloqueante para US-INV-01-04 (UI GR).
Esta story es el núcleo de la épica: implementa el MAP Engine que se ejecuta
cada vez que se confirma una Recepción de Mercancía (Goods Receipt).

Sigue el modelo de SAP MM Moving Average Price (MAP): en cada entrada de stock,
el nuevo MAP se calcula como `(stock_value_anterior + valor_nuevo_lote) / (qty_anterior + qty_nueva)`.

El pricing engine **no cambia**: sigue leyendo `costs.scheme_landed_aed`.
El MAP Engine simplemente actualiza ese valor al procesar cada GR.

## Descripción

Implementar `MAPEngine` (Celery task + service) que:
1. Lee la posición de inventario actual del SKU
2. Calcula el nuevo MAP con la fórmula WAC
3. Escribe `inventory_positions` (nueva posición)
4. Crea un `cost_lot` (capa del nuevo lote)
5. Llama `CostService.update_cost()` para actualizar `costs` (backwards compat)
6. Dispara `recalc_prices_by_sku` (Celery task existente)
7. Emite evento ERP vía adapter (NoOp por defecto)

## Criterios de Aceptación

### Celery Task
- [ ] Task `app/tasks/inventory.py`: `recalc_map_on_gr(gr_id: str) -> dict`
  registrada en Celery con `autoretry_for=(Exception,)`, `max_retries=3`,
  `default_retry_delay=30`
- [ ] Idempotente: si el GR ya tiene `status='processed'`, la task retorna sin modificar nada
- [ ] Al terminar: `goods_receipts.status = 'processed'`, `goods_receipts.processed_at = now()`
- [ ] En error (después de reintentos): `goods_receipts.status = 'error'`,
      escribe el traceback en `goods_receipts.notes`

### MAPService (lógica de dominio)
- [ ] Clase `app/services/inventory/map_service.py`: `MAPService`
- [ ] Método `calculate_map(sku, supplier_code, scheme_code, new_qty, new_unit_cost_aed) -> Decimal`:
  - Si no existe `inventory_position` previa: MAP = `new_unit_cost_aed` (primer lote)
  - Si existe: `MAP = (pos.total_stock_value_aed + new_qty * new_unit_cost_aed) / (pos.qty_on_hand + new_qty)`
  - Resultado redondeado a 4 decimales (ROUND_HALF_UP)
- [ ] Método `process_gr(gr_id: UUID, session: AsyncSession) -> InventoryPosition`:
  - Carga el GR con su `po_line` (join)
  - Convierte `actual_unit_price` a AED usando `actual_breakdown` (sufijos existentes)
    o fallback a `landed_cost_breakdown` del PO line si `actual_breakdown` está vacío
  - Llama `calculate_map()`
  - Escribe `GoodsReceipt.map_before`, `GoodsReceipt.map_after`
  - Upsert `inventory_positions` (INSERT ON CONFLICT DO UPDATE)
  - INSERT en `cost_lots` (nueva capa)
  - Llama `CostService.update_cost()` con breakdown reconstruido desde el GR
  - Retorna la `InventoryPosition` actualizada

### Integración con costs (backwards compat)
- [ ] El breakdown que se pasa a `CostService.update_cost()` se construye desde
      `goods_receipt.actual_breakdown` — si tiene las claves correctas, el trigger
      `costs_stamp_fx_trg` recalcula `scheme_landed_aed` normalmente
- [ ] Después del `update_cost()`, `costs.scheme_landed_aed` refleja el nuevo MAP
- [ ] `GET /api/v1/costs/{sku}` retorna el coste actualizado — sin cambios en la API

### Integración con pricing
- [ ] Al finalizar `process_gr()`, se dispara `recalc_prices_by_sku.delay(sku)` — task existente
- [ ] La re-propuesta de precios usa el nuevo `costs.scheme_landed_aed`

### Integración ERP (NoOp por defecto)
- [ ] Al finalizar `process_gr()`, se dispara `push_erp_event.delay(gr_id, 'goods_received')`
      (Celery task de US-INV-01-07 — en S12 W4 es NoOp)
- [ ] El dispatch al ERP no bloquea ni propaga excepciones al MAP Engine

### Tests
- [ ] `tests/services/inventory/test_map_service.py`:
  - `test_map_primer_lote`: qty=10, unit=11.20 AED → MAP=11.20
  - `test_map_segundo_lote`: pos anterior (10 uds × 11.20), nuevo (10 uds × 13.35) → MAP=12.275
  - `test_map_idempotente`: llamar `process_gr()` dos veces con mismo `gr_id` → sin cambio segunda vez
  - `test_map_actualiza_costs`: después de `process_gr()`, `cost.scheme_landed_aed == map_after`

## Notas Técnicas

- `calculate_map()` usa `Decimal` con `ROUND_HALF_UP` — consistente con `PricingRuleEngine`
- La conversión de moneda usa `CostService.compute_landed_aed()` (ya existe) pasando
  el `actual_breakdown` del GR — reutilizar la lógica, no duplicarla
- `inventory_positions` usa `INSERT ... ON CONFLICT (sku, supplier_code, scheme_code) DO UPDATE`
  para el upsert — evitar race conditions con `FOR UPDATE` en el SELECT previo
- El `recalc_prices_by_sku` existente ya hace fan-out por channels — no hay que tocar nada
- `push_erp_event` de US-INV-01-07 aún no existe en S12 W2; usar `if settings.ERP_ADAPTER != 'noop':`
  o simplemente loguear en INFO hasta que exista la task

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/services/inventory/__init__.py` | Crear |
| `app/services/inventory/map_service.py` | Crear (MAPService) |
| `app/tasks/inventory.py` | Crear (recalc_map_on_gr task) |
| `app/tasks/__init__.py` / `celery_app.py` | Modificar (registrar nueva task) |
| `tests/services/inventory/test_map_service.py` | Crear |

## Tests / Validación

```bash
pytest tests/services/inventory/test_map_service.py -v
# Expected: 4 tests pass

# Smoke manual:
# 1. Crear GR con actual_unit_price=13.35 AED para un SKU con posición existente
# 2. Ejecutar: celery call app.tasks.inventory.recalc_map_on_gr --args='["<gr_id>"]'
# 3. Verificar: inventory_positions.map_aed == nuevo MAP calculado
# 4. Verificar: costs.scheme_landed_aed == mismo MAP
# 5. Verificar: GR.status == 'processed'
```
