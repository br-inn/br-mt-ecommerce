# DR Drill Plan — Calendario y procedimiento (Sprint 6)

Complemento de [disaster-recovery.md](disaster-recovery.md). Define cómo y cuándo se ejecutan los drills y qué evidencia se persiste.

## 1. Cadencia

| Frecuencia | Tipo | Duración estimada |
|---|---|---|
| Mensual | Drill táctico (1 escenario sobre staging) | 2-4h |
| Trimestral | Drill estratégico (full DRP region-down) | 4-8h |
| Ad-hoc | Tras incidente o cambio infra mayor | variable |

## 2. Calendario inicial — 6 meses post-Hetzner deploy

| Mes target | Fecha objetivo | Escenario | Comando trigger | Owner | Reviewer |
|---|---|---|---|---|---|
| M+1 | 2026-06-07 | DB corruption sobre staging | `bash infra/scripts/dr-drill.sh db-corruption` | TI MT | Champion |
| M+2 | 2026-07-05 | Storage bucket loss sobre staging | `bash infra/scripts/dr-drill.sh storage-loss` | TI MT | R&D |
| M+3 | 2026-08-09 | Region down failover dry-run | `bash infra/scripts/dr-drill.sh region-failover` | TI MT | Full team |
| M+4 | 2026-09-06 | Compromised secrets rotation | `bash infra/scripts/dr-drill.sh secret-rotation` | TI MT | Champion |
| M+5 | 2026-10-04 | Live network cost cap kill-switch | `bash infra/scripts/dr-drill.sh kill-switch` | R&D | Champion |
| M+6 | 2026-11-08 | Full DRP — combinación 3+4 | `bash infra/scripts/dr-drill.sh full` | Full team | Sponsor |

Las fechas se actualizan tras cada drill — el siguiente queda pegged a +28 días.

## 3. Procedimiento estándar de un drill

### Pre-drill (T-7 días)
- [ ] Aviso por canal interno con escenario + ventana.
- [ ] Snapshot de DB staging vía `pg_dump` para revert.
- [ ] Backup de `audit_events` a CSV.
- [ ] Confirmar contactos on-call disponibles.

### Drill (T)
- [ ] Iniciar `audit_events` con `action='dr.drill_started'` y `entity_type='dr_drill'`.
- [ ] Ejecutar comando trigger según escenario.
- [ ] Cronometrar tiempos de detección, decisión, ejecución, validación.
- [ ] Documentar deviations sobre runbook.
- [ ] Cerrar con `audit_events action='dr.drill_completed'` con summary JSONB.

### Post-drill (T+1)
- [ ] Postmortem en `docs/runbooks/dr-postmortems/YYYY-MM-escenario.md`:
  - Tiempos vs target (RPO, RTO, detección, notificación).
  - Findings (3-5 bullets con WHAT + ROOT CAUSE).
  - Acciones (con owner + due date).
  - Riesgos descubiertos a añadir a `risk-register-consolidado.md`.
- [ ] Issue en GitHub por cada acción correctiva.
- [ ] Actualizar este calendario con próxima fecha.
- [ ] Actualizar tabla §4 de `disaster-recovery.md` (columna "Verificado").

## 4. Métricas de cobertura

| Métrica | Target | Cómo medir |
|---|---|---|
| % escenarios drill completados sin deviations | ≥ 80 % | postmortems |
| RTO real vs target (4h) | dentro target | cronometraje drill |
| RPO real vs target (24h) | dentro target | gap dump↔eventos |
| Findings críticos no resueltos > 30 días | 0 | issues abiertos |
| Drill participation rate | ≥ 80 % team disponible | attendance |

## 5. Escalation cuando un drill rompe staging

1. **Stop drill** inmediatamente — `bash infra/scripts/dr-drill.sh abort`.
2. **Restore staging** desde snapshot pre-drill.
3. **Alertar team** vía canal interno.
4. **Postmortem prioritario** dentro de 48h con: por qué la rotura aplica también a producción y qué cambia en el próximo drill.

## 6. Pendiente — Sprint 7

- [ ] Implementar `infra/scripts/dr-drill.sh` con sub-comandos (S6 deja stub).
- [ ] Tabla `dr_drills (id, scenario, started_at, completed_at, owner_id, summary JSONB)` con migración 030.
- [ ] Endpoint admin `/admin/dr-drills` para reporting al sponsor.
- [ ] Integración Sentry → monthly DR readiness score.
