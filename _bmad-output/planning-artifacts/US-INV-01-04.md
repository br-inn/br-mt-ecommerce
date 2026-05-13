# US-INV-01-04 — Goods Receipts: registro + UI

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 2 | **SP**: 8 | **Prioridad**: P0

## Contexto

Depende de US-INV-01-01 (modelo) y US-INV-01-02 (MAP Engine).
Esta story es el punto de entrada de datos que activa el MAP Engine: el usuario
registra la llegada real de mercancía, el sistema calcula el MAP automáticamente.

Sigue el flujo de SAP MIGO (Movement type 101 — Goods Receipt against PO).

## Descripción

Implementar el endpoint `POST /api/v1/goods-receipts` y la pantalla frontend
`/compras/recepciones`. Al confirmar una recepción, el sistema dispara
`recalc_map_on_gr.delay(gr_id)` en Celery y retorna inmediatamente con el GR creado
en estado `pending`. El usuario puede refrescar para ver `processed` y el MAP calculado.

## Criterios de Aceptación

### API
- [ ] `POST /api/v1/goods-receipts` — registra una recepción
      Body: `{po_line_id, qty_received, received_at?, actual_unit_price?, actual_breakdown?, notes?}`
      Valida:
      - `po_line_id` existe y el PO está en estado `confirmed` o `partial` (no `draft`)
      - `qty_received > 0`
      - `qty_received + po_line.qty_received <= po_line.qty_ordered` (no recibir más de lo pedido, warning si excede con override `force=true`)
      Acciones post-creación:
      - Actualiza `po_line.qty_received += qty_received`
      - Actualiza estado del PO: si `all lines received → 'received'`, else `'partial'`
      - Dispara `recalc_map_on_gr.delay(str(gr.id))`
      Retorna: GR creado con `status='pending'`
- [ ] `GET /api/v1/goods-receipts` — lista con filtros `?sku=&po_id=&status=` y paginación cursor
- [ ] `GET /api/v1/goods-receipts/{id}` — detalle con `map_before`, `map_after`,
      `po_line` (inline), `cost_lot` vinculado (una vez procesado)
- [ ] `GET /api/v1/goods-receipts/{id}/status` — endpoint polling ligero:
      retorna `{gr_id, status, map_before, map_after, processed_at}` — para UI polling
- [ ] Permiso requerido: `purchases:write`

### Schemas Pydantic
- [ ] `GoodsReceiptCreate`, `GoodsReceiptRead`, `GoodsReceiptStatusRead`
- [ ] `GoodsReceiptRead` incluye `po_line: PurchaseOrderLineRead` (join eager)

### Frontend — `/compras/recepciones`
- [ ] Página lista: tabla con columnas `GR#`, `SKU`, `PO#`, `Qty recibida`,
      `MAP antes`, `MAP después`, `Estado`, `Fecha recepción`
      Filtros: tabs Pendiente/Procesado/Error + búsqueda por SKU o PO#
- [ ] Badge estado: pending=amarillo (con spinner), processed=verde, error=rojo
- [ ] Botón "Registrar recepción" abre modal/Sheet:
      - Selector de PO (solo `confirmed`/`partial`)
      - Una vez elegido PO, selector de línea (SKU + qty pendiente)
      - Campo qty_received (máx = qty pendiente, con warning si se excede)
      - Sección "Coste real" (colapsable, opcional):
        - `actual_unit_price` — precio factura real (si difiere del PO)
        - Breakdown: `fob_eur`, `flete_eur`, `arancel_base_eur`, `arancel_pct`
        - Vista previa del coste aterrizaje AED calculado (llamada a `/costs/preview`)
      - Campo `notes`
- [ ] Al confirmar: el modal muestra estado `pending` con spinner y mensaje
      "Calculando Coste Medio Ponderado…"
- [ ] Polling automático cada 3s a `GET /goods-receipts/{id}/status` hasta `processed`
- [ ] Al llegar `processed`: muestra banner verde con:
      "MAP actualizado: {map_before} AED → {map_after} AED. Precios en recálculo."
- [ ] En caso de `error`: banner rojo con el mensaje del error + botón "Reintentar"
      que llama a `POST /api/v1/goods-receipts/{id}/retry` (ver abajo)
- [ ] Desde la lista de POs (`/compras/pedidos/[id]`): botón "Registrar recepción"
      en cada línea con qty pendiente — abre el mismo modal pre-cargado con esa línea

### API extra — retry
- [ ] `POST /api/v1/goods-receipts/{id}/retry` — re-encola `recalc_map_on_gr.delay(gr_id)`
      si `status = 'error'`. Resetea `status = 'pending'`.

## Notas Técnicas

- El polling de 3s en el frontend es suficiente para la mayoría de los casos
  (el MAP Engine tarda < 500ms en dev local). En producción usar WebSocket o
  SSE solo si el feedback del usuario indica que el polling es insuficiente.
- `actual_unit_price` y `actual_breakdown` son opcionales: si no se proveen,
  el MAP Engine usa el `unit_price` y `landed_cost_breakdown` de la línea del PO
- La vista previa del coste (`/costs/preview`) puede llamar a
  `CostService.compute_landed_aed()` existente — no crear nueva lógica
- El warning de "excede qty pedida" es útil en distribución (recepciones con exceso
  de proveedor son comunes); `force=true` en el body lo permite con audit en notes

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/api/routes/goods_receipts.py` | Crear |
| `app/api/router.py` | Modificar (registrar router) |
| `app/schemas/goods_receipts.py` | Crear |
| `app/repositories/goods_receipt.py` | Crear |
| `mt-pricing-frontend/app/(app)/compras/recepciones/page.tsx` | Crear |
| `mt-pricing-frontend/lib/api/endpoints/goods_receipts.ts` | Crear |
| `mt-pricing-frontend/components/compras/gr-form.tsx` | Crear (modal) |
| `mt-pricing-frontend/components/layout/sidebar.tsx` | Modificar (Compras→Recepciones) |

## Tests / Validación

```bash
pytest tests/api/test_goods_receipts.py -v
# Tests: crear GR, validar qty excede, estado PO actualizado, task disparada

# Smoke end-to-end:
# 1. Crear PO con 1 línea (SKU X, 10 uds, 10€)
# 2. Confirmar PO
# 3. Registrar GR: qty=10, actual_unit_price=11.20 AED
# 4. Verificar: GR.status = 'pending' al crear
# 5. Ejecutar worker Celery
# 6. Verificar: GR.status = 'processed', map_after = 11.20 AED
# 7. Verificar: inventory_positions.map_aed = 11.20
# 8. Verificar: costs.scheme_landed_aed actualizado
```
