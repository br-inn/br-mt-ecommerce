# Runbooks operacionales

Procedimientos operativos para incidentes, recuperación y mantenimiento.
Diseño base en
[`mt-dr-runbooks-sla-design.md`](../../_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md).

> **Estado**: la mayoría de los runbooks son **placeholders** y se completan
> a medida que se construyen / despliegan los módulos correspondientes.
> Antes del go-live a producción, los 15 deben estar en status `ready`.

---

## Índice de runbooks (RB-01 a RB-15)

| ID | Título | Categoría | Status | Sprint objetivo |
|---|---|---|---|---|
| RB-01 | Recuperación de DB Postgres (PITR + restore) | DR | placeholder | S3 |
| RB-02 | Failover de aplicación (rolling restart, redeploy) | DR | placeholder | S3 |
| RB-03 | Rotación de secretos (Doppler, JWT, API keys) | Seguridad | placeholder | S2 |
| RB-04 | Incidente de seguridad: contención y reporte | Seguridad | placeholder | S3 |
| RB-05 | Pipeline de migraciones falla en deploy | DB | placeholder | S2 |
| RB-06 | Backlog de jobs Celery: diagnóstico y drenado | Jobs | placeholder | S2 |
| RB-07 | Caída de Redis (cache + broker) | Jobs / Infra | placeholder | S3 |
| RB-08 | Healthcheck rojo en api / worker / beat | Operability | placeholder | S2 |
| RB-09 | Saturación de base de datos: long queries y locks | DB / Performance | placeholder | S3 |
| RB-10 | Incidente de comparator (scraping bloqueado, OCR fallando) | Producto | placeholder | S3 |
| RB-11 | Recuperación de Caddy / TLS expirado | Infra | placeholder | S2 |
| RB-12 | Procedimiento de release y rollback | CI/CD | placeholder | S2 |
| RB-13 | Onboarding / offboarding de usuarios y rotación de roles | Seguridad | placeholder | S2 |
| RB-14 | Incidente de performance frontend (build, runtime, CDN) | Frontend | placeholder | S3 |
| RB-15 | DR completo: restauración multi-componente desde backup | DR | placeholder | S4 |

---

## Plantilla de runbook

Cada runbook incluye:

1. **Trigger** — qué condición o alerta dispara su ejecución.
2. **Severidad** — SEV1/2/3 según
   [SLO doc](../../_bmad-output/planning-artifacts/adr/ADR-052-sli-slo-error-budget.md).
3. **Pre-requisitos** — accesos, herramientas, contactos.
4. **Pasos** — comandos exactos, copy-paste-friendly, idempotentes cuando se
   pueda.
5. **Verificación** — cómo confirmar que el sistema volvió a estado normal.
6. **Comunicación** — quién avisa a quién, cadencia de updates.
7. **Post-mortem** — cuándo es obligatorio (SEV1 siempre; SEV2 si tarda > X).
8. **Mejoras** — referencias a issues abiertos para no volver a pisar lo
   mismo.

Ubicación una vez escritos: `docs/runbooks/RB-XX-<slug>.md`.

---

## Drills y mantenimiento

- **Drill DR**: 1× por trimestre, ejecutando RB-01 + RB-15 en staging.
- **Auditoría de runbooks**: revisión trimestral de freshness (¿siguen
  vigentes los comandos? ¿cambió algún path?).
- Cualquier incidente real **debe** generar un PR para actualizar el runbook
  correspondiente con lo aprendido.
