---
title: "MT Pricing — Cutover Gate Signoff"
project: "MT Middle East MDM + Pricing Fase 1"
version: "1.0"
status: "PENDING"   # cambiar a SIGNED cuando todos firmen
---

# Cutover Gate — MT Pricing Fase 1

> Este documento debe estar en estado **SIGNED** antes de activar la plataforma en producción y archivar el Excel de referencia.

## Checklist de precondiciones

Todos los items deben estar en ✅ verde antes de proceder al cutover.

### Datos y migración

- [ ] **Migración de datos completa**: 100% de SKUs activos importados en la plataforma
- [ ] **0 diferencias durante ≥ 5 días consecutivos**: El reporte `parallel-run-diff-YYYY-MM-DD.csv` muestra 0 discrepancias durante al menos 5 días seguidos (flag `cutover_ready=true` en sistema)
- [ ] **Auditoría verificada**: ≥ 50 eventos de aprobación en `audit_events` confirmando trazabilidad

### Operaciones

- [ ] **Backup Operator listo**: `docs/training-log.md` muestra status `completed` con firma del Backup Operator
- [ ] **Manual aprobado**: `docs/handbook-es.md` revisado y aprobado por Champion (psierra)
- [ ] **Rollback playbook verificado**: Drill de rollback ejecutado en `docs/drill-log.md` con outcome `pass`
- [ ] **DR runbook accesible**: `docs/runbooks/runbook-cutover.md` disponible y actualizado

### Técnico

- [ ] **Health check API**: `GET /health` retorna 200 en entorno de producción
- [ ] **Performance validada**: p95 latencia endpoints CRUD < 250 ms (NFR-06)
- [ ] **Monitoreo activo**: Dashboards observabilidad configurados y alertas activas

### Post-cutover inmediato

- [ ] **Excel archivado**: `stock_dubai_v23` renombrado a `stock_dubai_v23_ARCHIVE_YYYY-MM-DD` (read-only)
- [ ] **Excel accesible 90 días**: Backup en Supabase Storage `price-reference-excel/archive/`

---

## Verificación del flag `cutover_ready`

El parallel run genera un reporte diario de diferencias entre precios del Excel de referencia y los precios en la plataforma. Para verificar el estado del flag antes de firmar:

```bash
# Consultar directamente en Supabase (tabla parallel_run_status o similar)
# Verificar que cutover_ready = true durante ≥ 5 días consecutivos
# Los reportes CSV se ubican en: Supabase Storage > price-reference-excel/parallel-run/

# Ejemplo de verificación manual del reporte más reciente:
# parallel-run-diff-YYYY-MM-DD.csv debe tener 0 filas de diferencias
```

> **Nota**: A la fecha de implementación (2026-05-12) no existe un endpoint `/parallel-run` en el backend. La verificación es manual via los reportes CSV descargados de Supabase Storage. Cuando se automatice, este documento debe actualizarse con la URL del endpoint.

---

## Registro de evaluación

| Item | Estado | Fecha verificación | Verificado por |
|------|--------|-------------------|----------------|
| Migración completa | PENDING | — | — |
| 0 diff ≥ 5 días | PENDING | — | — |
| Auditoría ≥ 50 eventos | PENDING | — | — |
| Backup Operator listo | PENDING | — | — |
| Manual aprobado | PENDING | — | — |
| Rollback drill pass | PENDING | — | — |
| DR runbook | PENDING | — | — |
| Health check | PENDING | — | — |
| Performance validada | PENDING | — | — |
| Monitoreo activo | PENDING | — | — |

---

## Estado actual de dependencias (2026-05-12)

| Artefacto | Archivo | Estado actual |
|-----------|---------|--------------|
| Parallel run | `docs/parallel-run-diff-*.csv` | Pendiente ejecución |
| Training log | `docs/training-log.md` | `pending` — sesiones y firma pendientes |
| Handbook | `docs/handbook-es.md` | Creado, aprobación formal pendiente |
| Drill log | `docs/drill-log.md` | Drill planificado 2026-06-07, `pending` |
| Runbook cutover | `docs/runbooks/runbook-cutover.md` | Disponible ✓ |
| E2E validación | `docs/e2e-validation.md` | Flujos cubiertos ✓ |

---

## Firmas

**Instrucciones**: Cada firmante debe completar su fila con fecha y firma (iniciales o nombre completo). El campo `status` del frontmatter debe cambiarse a `SIGNED` cuando los 3 firmantes hayan completado.

| Rol | Nombre | Empresa | Fecha | Firma |
|-----|--------|---------|-------|-------|
| Gerente de Pricing | [PENDIENTE] | MT Middle East | — | _____ |
| TI Integración | [PENDIENTE] | MT Middle East | — | _____ |
| Sponsor | [PENDIENTE] | BR Innovation | — | _____ |
| Champion (testigo) | psierra | BR Innovation | — | _____ |

---

## Post-cutover

Una vez firmado y activado:

1. Actualizar este documento: `status: SIGNED`
2. Ejecutar en producción:
   ```bash
   # Archivar Excel
   # (proceso manual o via API endpoint /admin/exports/reference-excel/archive)
   ```
3. Notificar a todos los stakeholders por email
4. Programar review post-cutover a 7 días

---

*Generado: 2026-05-12 — Sprint 8 — US-1B-05-05*
*Dependencias: US-1B-05-01 (parallel run) ✅ | US-1B-05-02 (handbook) ✅ | US-1B-05-03 (training) ✅ | US-1B-05-04 (rollback playbook) ✅*
