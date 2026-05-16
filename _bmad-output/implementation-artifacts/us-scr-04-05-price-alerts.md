# US-SCR-04-05 — Price Alerts pg_notify + Heartbeat 26h + Email SendGrid

**Epic**: EP-SCR-04 — Monitoreo Autónomo + Price Intelligence  
**Sprint**: S15  
**Story Points**: 8 SP  
**Estado**: review  
**Fecha**: 2026-05-16

## Verificación de existencia

Todos los componentes existían ya implementados por el agente ERP-Backend en sesión anterior.

## Componentes implementados

### Migración Alembic
- **Archivo**: `mt-pricing-backend/alembic/versions/20260602_135_price_alerts.py`
- `down_revision = "20260601_134"` (encadenada correctamente)
- Tabla `price_alerts(id, match_id, sku, marketplace, alert_type, threshold_pct, prev_price_aed, current_price_aed, variation_pct, triggered_at, notified_at, channel)`
- Función PL/pgSQL `notify_price_alert()` que emite `pg_notify('price_alert', payload_json)`
- Trigger `trg_price_alert_notify` AFTER INSERT
- Seed en `job_definitions`: `send_price_alert_emails` (cron `*/5 * * * *`) y `scraper_heartbeat` (cron `0 */26 * * *`)

### Modelo ORM
- **Archivo**: `mt-pricing-backend/app/db/models/price_alerts.py`
- Clase `PriceAlert(Base)` con todos los campos de la migración
- Registrado en `app/db/models/__init__.py` ← **AÑADIDO en esta sesión**

### Celery Tasks (en `price_monitor.py`)
- `send_price_alert_emails`: carga alertas con `notified_at IS NULL`, envía via SendGrid si `SENDGRID_API_KEY` está configurado; log warning si no → no crash
- `scraper_heartbeat`: UPDATE `job_definitions.last_run_at` para códigos `scraper_heartbeat`

### Integración en price_monitor_task
- Detecta variación ≥ 5% vs precio anterior
- INSERT `PriceAlert` cuando hay variación
- El trigger DB emite `pg_notify` automáticamente

## Notas
- Si `SENDGRID_API_KEY` no está configurado: log warning, retorna `{status: "skipped"}`
- pg_notify canal: `price_alert`
- Heartbeat intervalo: 26h (cron `0 */26 * * *`)
