# US-INV-01-07 — ERP Webhooks Outbound + Event Log

**Épica**: EP-INV-01 (Inventory Costing) | **Sprint**: S12 Wave 4 | **SP**: 5 | **Prioridad**: P2

## Contexto

Depende de US-INV-01-06 (adapter layer). Es la plomería que hace que los adapters
reales (SAP/Odoo) puedan recibir eventos de MT de forma fiable cuando se conecten.
Implementa el patrón "transactional outbox" para garantizar que ningún evento se
pierda aunque el ERP esté temporalmente caído.

## Descripción

Implementar la tabla `erp_sync_events` (outbox pattern), la Celery task
`push_erp_event` con reintentos exponenciales, firma HMAC-256 en los payloads,
y la UI de administración del log de eventos en `/admin/erp-eventos`.

## Criterios de Aceptación

### Tabla erp_sync_events (migración 20260512_095)
- [ ] Columnas: `id UUID PK`, `event_type VARCHAR(64) NOT NULL`,
      `entity_id VARCHAR(128)` (gr_id o map_update ref),
      `payload JSONB NOT NULL`, `adapter VARCHAR(32) NOT NULL DEFAULT 'noop'`,
      `status VARCHAR(32) NOT NULL DEFAULT 'pending'`
      CHECK `status IN ('pending','delivered','failed','skipped')`,
      `attempts INT NOT NULL DEFAULT 0`,
      `last_attempted_at TIMESTAMP TZ`, `last_error TEXT`,
      `delivered_at TIMESTAMP TZ`, `external_ref VARCHAR(256)` (ref del ERP),
      `created_at`, `updated_at`
- [ ] Index `idx_erp_sync_pending` partial: `WHERE status = 'pending'`
- [ ] Index `idx_erp_sync_entity` on `(entity_id, event_type)`
- [ ] Modelo SQLAlchemy `ERPSyncEvent` en `app/db/models/inventory.py`

### Celery Task `push_erp_event`
- [ ] `app/tasks/erp_sync.py`: task `push_erp_event(event_id: str)`
      - Carga `ERPSyncEvent` por id, verifica `status = 'pending'`
      - Si `ERP_ADAPTER = 'noop'`: marca `status = 'skipped'`, retorna
      - Construye el evento tipado (`GoodsReceivedEvent` o `MAPUpdatedEvent`) desde `payload`
      - Llama el método correcto del adapter según `event_type`
      - HMAC-256: firma `json.dumps(payload, sort_keys=True)` con `ERP_WEBHOOK_SECRET`
        y agrega header `X-MT-Signature: sha256={hex}` (para adapters HTTP futuros)
      - En éxito: `status = 'delivered'`, `external_ref = ref_retornado`, `delivered_at = now()`
      - En excepción: incrementa `attempts`, guarda `last_error`, `last_attempted_at`
      - Retry exponencial: `countdown = 60 * 2^attempts`, max `attempts = 5`
      - Tras 5 intentos fallidos: `status = 'failed'` (no más reintentos)

### Creación de eventos desde MAP Engine
- [ ] En `app/tasks/inventory.recalc_map_on_gr`: tras `process_gr()` exitoso,
      crear `ERPSyncEvent` con `event_type='goods_received'`, `entity_id=gr_id`,
      `payload=GoodsReceivedEvent(...)` serializado como dict
      Luego: `push_erp_event.delay(str(sync_event.id))`
- [ ] Mismo patrón para `MAPUpdatedEvent` (event_type='map_updated')

### UI Admin — `/admin/erp-eventos`
- [ ] Tabla con columnas: `Tipo`, `Entity ID`, `Adapter`, `Estado`, `Intentos`,
      `Último error`, `Entregado en`, `Fecha`
- [ ] Filtros: tab Pendientes / Entregados / Fallidos / Omitidos
- [ ] Botón "Reintentar" en filas `failed` → `PATCH /api/v1/admin/erp-eventos/{id}/retry`
      que resetea `status = 'pending'`, `attempts = 0` y re-encola la task
- [ ] Solo visible para rol `admin`
- [ ] Muestra `external_ref` (ref del ERP) en filas `delivered`

### API Admin
- [ ] `GET /api/v1/admin/erp-eventos` — lista con filtros + cursor pagination
- [ ] `PATCH /api/v1/admin/erp-eventos/{id}/retry` — resetea y re-encola

## Notas Técnicas

- El patrón "transactional outbox" garantiza que si el MAP Engine falla a mitad,
  el evento ERP no se envía (la row en `erp_sync_events` nunca se crea)
- HMAC firma el payload completo — cuando el adapter HTTP real lea esto, podrá
  verificar la autenticidad antes de procesar. `ERP_WEBHOOK_SECRET` vacío = sin firma
- Con `ERP_ADAPTER = 'noop'`, todos los eventos se marcan `skipped` inmediatamente —
  sin ruido en el log de fallos
- La tabla `erp_sync_events` sirve también de audit trail: si el cliente pregunta
  "¿cuándo se envió este GR a SAP?", está aquí

## Archivos a Crear/Modificar

| Archivo | Acción |
|---------|--------|
| `alembic/versions/20260512_095_erp_sync_events.py` | Crear |
| `app/db/models/inventory.py` | Modificar (añadir ERPSyncEvent) |
| `app/tasks/erp_sync.py` | Crear |
| `app/tasks/inventory.py` | Modificar (crear ERPSyncEvent post-GR) |
| `app/api/routes/admin.py` | Modificar (erp-eventos endpoints) |
| `mt-pricing-frontend/app/(app)/admin/erp-eventos/page.tsx` | Crear |
| `mt-pricing-frontend/lib/api/endpoints/erp_sync.ts` | Crear |

## Tests / Validación

```bash
pytest tests/tasks/test_erp_sync.py -v
# test_skip_on_noop_adapter
# test_delivered_on_success
# test_retry_on_failure
# test_failed_after_max_retries

# Smoke UI:
# 1. Registrar un GR → erp_sync_events crea fila con status='skipped' (NoOp)
# 2. Ir a /admin/erp-eventos → fila visible en tab "Omitidos"
# 3. Cambiar ERP_ADAPTER=sap (stub) → GR nuevo → fila 'failed' (NotImplementedError)
# 4. Botón Reintentar → re-encola task
```
