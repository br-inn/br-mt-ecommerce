# ADR-076 — Audit Log Hash Chain (Tamper-Evident)

**Status:** Accepted
**Date:** 2026-05-12
**Closes:** R-005 (Risk Register), gap A13 (Production Readiness)
**Migration:** `alembic/versions/20260519_076_audit_hash_chain.py`

## Context

UAE VAT 2026 exige registros contables tamper-evident. `audit_events` es
append-only por policy de aplicación pero un superuser Postgres puede modificar
filas directamente. Se necesita garantía criptográfica detectable por terceros
auditores sin acceso a privilegios de superusuario.

El modelo `AuditEvent` ya tenía las columnas `prev_hash` y `current_hash`
(nullable, sin trigger activo hasta esta migración). Esta ADR activa el
mecanismo completo.

## Decision

Implementar hash chain via trigger `BEFORE INSERT` en PostgreSQL:

```
current_hash = sha256(
    id || event_at || actor_id || entity_type || entity_id ||
    action || payload_diff || prev_hash
)
```

### Componentes

1. **Tabla `audit_hash_state`** — singleton (una fila, `id=1`) que almacena
   el `last_hash` del chain. Evita full-scan de la tabla particionada para
   obtener el hash anterior. El trigger hace `SELECT ... FOR UPDATE` sobre esta
   fila para serializar inserts concurrentes.

2. **Función `compute_audit_hash()`** — PL/pgSQL `SECURITY DEFINER` que calcula
   `sha256()` nativo de Postgres. Se ejecuta en cada INSERT en `audit_events`.

3. **Trigger `trg_audit_hash_before_insert`** — `BEFORE INSERT FOR EACH ROW`
   sobre la tabla particionada (aplica a todas las particiones hijas).

4. **REVOKE UPDATE/DELETE** sobre `audit_events` desde `mt_app` y `PUBLIC` —
   enforza append-only a nivel de privilegio de BD.

5. **Tabla `audit_chain_signatures`** — persiste la firma HMAC-SHA256 diaria del
   último hash (generada por el job nocturno). Cada fila es evidencia auditable
   para un rango día × firma.

6. **Job `audit.nightly_integrity_check`** — Celery task (03:00 Asia/Dubai)
   que verifica el chain del día anterior y firma el último hash con
   `AUDIT_SIGNING_KEY` (HMAC-SHA256, clave de 32 bytes en base64).

7. **Endpoint `GET /api/v1/audit/verify`** — verificación ad-hoc para auditores,
   rango máximo 7 días, retorna HTTP 409 si detecta tamper.

### Concatenación del hash (Python ↔ SQL)

La concatenación es idéntica en el trigger SQL y en la verificación Python:

```python
row_data = (
    str(id)          # COALESCE(NEW.id::TEXT, '')
    + event_at_iso   # COALESCE(NEW.event_at::TEXT, '')
    + str(actor_id)  # COALESCE(NEW.actor_id::TEXT, '')
    + entity_type    # COALESCE(NEW.entity_type, '')
    + entity_id      # COALESCE(NEW.entity_id, '')
    + action         # COALESCE(NEW.action, '')
    + payload_json   # COALESCE(NEW.payload_diff::TEXT, '{}')
    + prev_hash      # COALESCE(prev_h, '')
)
```

Los valores `NULL` se colapsan a `''` en ambas implementaciones.

## Consequences

### Positivas
- Cualquier modificación de una fila produce un hash incorrecto detectable
  en el siguiente ciclo de verificación nightly (máx 24h lag).
- La firma HMAC diaria en `audit_chain_signatures` permite auditoría externa
  sin acceso a la BD.
- `GET /audit/verify` permite verificaciones ad-hoc bajo demanda.
- REVOKE UPDATE/DELETE cierra el vector de modificación desde `mt_app`.

### Negativas / Trade-offs
- Los INSERTs en `audit_events` adquieren un lock advisory sobre la fila
  singleton de `audit_hash_state` — serializa escrituras concurrentes.
  Aceptable para volumen estimado <1k eventos/día en Fase 1.
- Si el trigger falla (e.g. corrupción de `audit_hash_state`), el INSERT
  completo falla — el audit event se pierde. Mitigación: monitoreo de la tabla
  singleton en el healthcheck.
- La serialización via singleton limita throughput de audit writes. Para
  volúmenes >10k/día considerar batching o hash tree (fuera de alcance Fase 1).

## Alternatives Rejected

| Alternativa | Razón de rechazo |
|---|---|
| WORM backup (S3 Object Lock) | No detecta tamper en tiempo real; auditor debe comparar dumps |
| Blockchain / Hyperledger | Over-engineering para volumen <1k eventos/día; latencia y coste operativo |
| Trigger async (NOTIFY) | Race condition entre INSERT y notificación; no garantiza atomicidad |
| Firma por fila (sin chain) | No detecta inserciones/eliminaciones de filas, solo modificaciones |

## References

- R-005 Risk Register — "Audit log integrity (UAE VAT 2026)"
- UAE Federal Decree-Law No. 8 of 2017 (VAT) — Art. 78: registros electrónicos deben ser íntegros y auditables
- ADR-049 — Migration discipline (Alembic sync)
- `app/workers/tasks/audit_integrity.py` — implementación del job nightly
- `app/api/routes/audit.py` — endpoint `GET /audit/verify`
