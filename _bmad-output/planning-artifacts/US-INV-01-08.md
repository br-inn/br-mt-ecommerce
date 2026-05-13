# US-INV-01-08 — Migración backwards-compat: seed inventory_positions desde costs existentes

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 1 | **SP**: 3 | **Prioridad**: P0 — BLOQUEANTE

## Contexto

Depende de US-INV-01-01 (modelo de datos). Debe ejecutarse junto con las migraciones
Alembic de US-INV-01-01 para que el sistema quede en estado consistente desde el
primer despliegue de la épica.

El sistema tiene ~224 SKUs con costes registrados manualmente en la tabla `costs`.
Al añadir `inventory_positions`, esos costes existentes necesitan tener una posición
de inventario correspondiente para que:
1. `MAPService.calculate_map()` encuentre el estado previo correcto al procesar el primer GR
2. El dashboard de inventario muestre los SKUs con su coste actual aunque no tengan GRs aún
3. No haya datos huérfanos

## Descripción

Crear un script de migración de datos (`scripts/seed_inventory_positions.py`) y
un endpoint de administración para ejecutarlo de forma controlada. También verificar
que los endpoints existentes de `costs` siguen funcionando sin cambios.

## Criterios de Aceptación

### Script de seed
- [ ] `scripts/seed_inventory_positions.py`:
      - Lee todos los `Cost` con `status = 'active'`
      - Por cada cost, crea o actualiza `InventoryPosition`:
        ```
        INSERT INTO inventory_positions (sku, supplier_code, scheme_code,
            qty_on_hand, map_aed, total_stock_value_aed, last_updated_at)
        VALUES (cost.sku, cost.supplier_code, cost.scheme_code,
            0,                        -- qty_on_hand = 0 (aún sin GRs)
            cost.scheme_landed_aed,   -- MAP inicial = coste actual
            0,                        -- valor = 0 porque qty = 0
            cost.created_at)
        ON CONFLICT (sku, supplier_code, scheme_code) DO NOTHING
        ```
      - Loguea: `Seeded {n} inventory positions from existing costs`
      - Idempotente: ejecutar dos veces produce el mismo resultado (ON CONFLICT DO NOTHING)
- [ ] El script se puede ejecutar con: `python scripts/seed_inventory_positions.py`
      y también está referenciado en `infra/scripts/migrate.sh` para ejecutarse
      automáticamente después de `alembic upgrade head`

### Endpoint admin (para re-seed si es necesario)
- [ ] `POST /api/v1/admin/inventory/seed-from-costs` — rol `admin` requerido
      - Ejecuta la misma lógica del script
      - Retorna `{seeded: n, skipped: m, total_costs: n+m}`
      - Idempotente

### Verificación backwards compat
- [ ] `GET /api/v1/costs` — responde igual que antes (sin cambios)
- [ ] `POST /api/v1/costs` — crea coste, no crea `inventory_position` automáticamente
      (los costes manuales no tienen GR, la posición se crea en el seed o cuando llegue el primer GR)
- [ ] `PUT /api/v1/costs/{id}` — actualiza coste, no toca `inventory_positions`
      (la actualización manual de costes sigue funcionando como fallback para SKUs
      que se gestionan por precio de referencia y no por GRs)
- [ ] Pricing engine: `rule_engine.py` sigue leyendo `cost.scheme_landed_aed` — sin cambios

### Test de regresión
- [ ] `tests/api/test_costs_backwards_compat.py`:
      - `test_get_costs_unchanged`: GET /costs retorna las mismas columnas que antes
      - `test_post_costs_unchanged`: POST /costs crea coste sin tocar inventory_positions
      - `test_pricing_uses_costs_unchanged`: simular precio usa costs.scheme_landed_aed

## Notas Técnicas

- `qty_on_hand = 0` en el seed es correcto: estos SKUs tienen coste registrado
  manualmente pero no tienen inventario trackeado. Al registrar el primer GR real,
  el MAP Engine calculará `MAP = actual_unit_cost` (primer lote) y lo sobrescribirá.
- `supplier_code` en `costs` puede ser `NULL` (costes globales). En ese caso, usar
  `supplier_code = '__default__'` en `inventory_positions` para mantener la UNIQUE constraint.
  Documentar este workaround en el código.
- No modificar `infra/scripts/migrate.sh` sin validar que funciona en Docker local primero.

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `scripts/seed_inventory_positions.py` | Crear |
| `infra/scripts/migrate.sh` | Modificar (call seed script post-migrate) |
| `app/api/routes/admin.py` | Modificar (POST /inventory/seed-from-costs) |
| `tests/api/test_costs_backwards_compat.py` | Crear |

## Tests / Validación

```bash
# 1. Con DB limpia y costes existentes:
alembic upgrade head
python scripts/seed_inventory_positions.py
# Output: "Seeded 47 inventory positions from existing costs" (o el número real)

# 2. Segunda ejecución (idempotente):
python scripts/seed_inventory_positions.py
# Output: "Seeded 0 inventory positions from existing costs"

# 3. Regresión:
pytest tests/api/test_costs_backwards_compat.py -v
# Expected: 3 tests pass

# 4. Smoke endpoint:
# POST /api/v1/admin/inventory/seed-from-costs → {seeded: 0, skipped: 47, total_costs: 47}
```
