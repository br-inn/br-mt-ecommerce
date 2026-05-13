# US-INV-01-03 — Purchase Orders CRUD + UI

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 2 | **SP**: 8 | **Prioridad**: P1

## Contexto

Depende de US-INV-01-01 (modelo). Puede desarrollarse en paralelo con US-INV-01-02 y 04.
Provee la gestión de Pedidos de Compra que precede a la recepción de mercancía.
Sigue el flujo estándar de ERP: `PO draft → confirmed → partial → received | cancelled`.

## Descripción

Implementar API REST completa para `purchase_orders` y `purchase_order_lines`,
y la pantalla frontend `/compras/pedidos` con lista, creación y detalle/edición.
Permiso requerido: `purchases:write` (rol TI Integración + admin).

## Criterios de Aceptación

### API — Purchase Orders
- [ ] `POST /api/v1/purchase-orders` — crea PO en estado `draft`
      Body: `{po_number, supplier_code, currency, notes?, lines: [{sku, scheme_code, qty_ordered, unit_price, landed_cost_breakdown}]}`
      Valida: `po_number` único, `supplier_code` existe, `sku` existe por cada línea
- [ ] `GET /api/v1/purchase-orders` — lista con filtros `?supplier_code=&status=&q=` y paginación cursor
- [ ] `GET /api/v1/purchase-orders/{id}` — detalle con líneas y GRs asociados
- [ ] `PUT /api/v1/purchase-orders/{id}` — actualiza PO (solo en estado `draft`)
      Si el PO está en otro estado, retorna 422 con mensaje claro
- [ ] `POST /api/v1/purchase-orders/{id}/confirm` — `draft → confirmed`
      Valida que tenga al menos 1 línea con `qty_ordered > 0`
- [ ] `POST /api/v1/purchase-orders/{id}/cancel` — cualquier estado → `cancelled`
      Solo si no hay GRs procesados asociados (422 si los hay)
- [ ] `DELETE /api/v1/purchase-orders/{id}` — solo en estado `draft`, soft-delete o hard-delete
- [ ] Todos los endpoints requieren permiso `purchases:write`

### API — Purchase Order Lines
- [ ] `POST /api/v1/purchase-orders/{id}/lines` — agrega línea (solo si PO en `draft`)
- [ ] `PUT /api/v1/purchase-orders/{id}/lines/{line_id}` — edita línea (solo si PO en `draft`)
- [ ] `DELETE /api/v1/purchase-orders/{id}/lines/{line_id}` — elimina línea (solo si PO en `draft`)

### Schemas Pydantic
- [ ] `PurchaseOrderCreate`, `PurchaseOrderRead`, `PurchaseOrderUpdate`
- [ ] `PurchaseOrderLineCreate`, `PurchaseOrderLineRead`
- [ ] `PurchaseOrderReadDetail` (incluye `lines: list[PurchaseOrderLineRead]` + `gr_count: int`)

### Frontend — `/compras/pedidos`
- [ ] Página lista: tabla con columnas `PO#`, `Proveedor`, `Estado`, `Líneas`, `Fecha`, `Acciones`
      Filtros: `?status=` (tabs: Todos/Borrador/Confirmado/Recibido/Cancelado) + búsqueda por PO#
- [ ] Badge de estado con colores: draft=gris, confirmed=azul, partial=amarillo,
      received=verde, cancelled=rojo
- [ ] Botón "Nuevo pedido" abre Sheet lateral con formulario:
      - Campo PO#, selector proveedor, moneda
      - Tabla de líneas inline: agregar/eliminar líneas con SKU selector, qty, precio unitario
      - Breakdown de costes de aterrizaje por línea (expandible): campos `fob_eur`, `flete_eur`, `arancel_base_eur`, `arancel_pct`
- [ ] Página detalle `/compras/pedidos/[id]`:
      - Header con datos del PO + badge estado + botones de acción (Confirmar / Cancelar)
      - Tabla de líneas con qty_ordered, qty_received, unit_price, breakdown
      - Sección "Recepciones" (read-only en esta story) — lista de GRs vinculados
- [ ] Toast de confirmación al crear/actualizar/confirmar/cancelar

### Permisos frontend
- [ ] Botones de mutación solo visibles para usuarios con `purchases:write`
- [ ] Página accesible para todos los roles (read-only sin permiso)

## Notas Técnicas

- Seguir el patrón de paginación cursor existente en `/precios` (campo `next_cursor`)
- El selector de SKU en líneas puede reusar el componente de búsqueda del catálogo
- `landed_cost_breakdown` en el formulario: usar los mismos campos que ya conoce el
  usuario de la pantalla de costes manual — consistencia UX importante
- Los cálculos de coste de aterrizaje en el formulario son **indicativos** (no se persisten
  como coste hasta que llegue el GR y el MAP Engine los procese)
- Ruta en sidebar: "Compras" → "Pedidos" (nuevo ítem de navegación)

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `app/api/routes/purchase_orders.py` | Crear |
| `app/api/router.py` | Modificar (registrar router) |
| `app/schemas/purchase_orders.py` | Crear |
| `app/repositories/purchase_order.py` | Crear |
| `mt-pricing-frontend/app/(app)/compras/pedidos/page.tsx` | Crear |
| `mt-pricing-frontend/app/(app)/compras/pedidos/[id]/page.tsx` | Crear |
| `mt-pricing-frontend/lib/api/endpoints/purchase_orders.ts` | Crear |
| `mt-pricing-frontend/components/compras/po-form.tsx` | Crear |
| `mt-pricing-frontend/components/layout/sidebar.tsx` | Modificar (nuevo ítem) |

## Tests / Validación

```bash
pytest tests/api/test_purchase_orders.py -v
# Tests: crear PO, confirmar, cancelar, validar estado
# Happy path + error cases (PO en estado incorrecto, SKU inexistente)

# Smoke UI:
# 1. Ir a /compras/pedidos — lista vacía correcta
# 2. Crear PO con 2 líneas → aparece en lista como "Borrador"
# 3. Confirmar PO → badge cambia a "Confirmado"
# 4. Cancelar PO confirmado sin GRs → estado "Cancelado"
```
