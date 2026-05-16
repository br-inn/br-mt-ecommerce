# US-SCR-04-08b — HITL Queue Scoring Uncertainty×Value + High-Value Threshold AED 1K

**Epic**: EP-SCR-04 — Monitoreo Autónomo + Price Intelligence  
**Sprint**: S16  
**Story Points**: 5 SP  
**Estado**: review  
**Fecha**: 2026-05-16

## Verificación de existencia

Todos los componentes existían implementados.

## Componentes implementados

### Migración Alembic
- **Archivo**: `mt-pricing-backend/alembic/versions/20260602_136_hitl_queue.py`
- `down_revision = "20260602_135"` (encadenada después de price_alerts)
- Este es el HEAD actual: `20260602_136 (head)` ✅
- Tabla `hitl_queue(id, match_id, uncertainty_score, product_value_aed, priority_score, status, assigned_to, notes, created_at, updated_at)`
- Índices: `ix_hitl_queue_priority`, `ix_hitl_queue_status_priority`, `ix_hitl_queue_match_id`

### Modelo ORM
- **Archivo**: `mt-pricing-backend/app/db/models/hitl_queue.py`
- Clase `HitlQueue(Base)` + constantes `HITL_CONFIDENCE_THRESHOLD = 0.6`, `HITL_VALUE_THRESHOLD_AED = 1000`
- Registrado en `app/db/models/__init__.py` ← **AÑADIDO en esta sesión**

### Endpoints REST
- **Archivo**: `mt-pricing-backend/app/api/routes/hitl_queue_price.py`
- Registrado en `app/api/routes/__init__.py`

#### GET `/api/v1/matching/hitl-queue`
- Lista ordenada por `priority_score DESC`
- Filtro opcional por `status`
- Paginación `limit/offset`
- RBAC: `products:read`

#### PATCH `/api/v1/matching/hitl-queue/{id}`
- Actualiza `status` (pending/approved/rejected/skipped) y `notes`
- RBAC: `products:write`

### Auto-enqueue en Match Pipeline
- **Archivo**: `mt-pricing-backend/app/services/matching/match_service.py`
- Método `_maybe_enqueue_hitl()` + `__maybe_enqueue_hitl_impl()`
- Condición: `confidence < 0.6 AND product_value > 1000 AED`
- `priority_score = uncertainty_score × product_value_aed`
- Errores de enqueue capturados silenciosamente (no bloquean el pipeline)

## Fórmula de priorización
```
priority_score = uncertainty_score × product_value_aed
```
- `uncertainty_score = 1.0 - calibrated_confidence` (o `1.0 - score/100` si no hay calibrated_confidence)
- Ej: producto AED 5000 con confidence 0.3 → `priority_score = 0.7 × 5000 = 3500`
