# Runbook de Cutover — MT Pricing MDM

**Historia**: US-1B-05-04
**Sprint**: Sprint 8
**Fecha de creación**: 2026-05-12
**Owner técnico**: psierra@br-innovation.com
**Ámbito**: stack `mt-pricing-mdm-phase1` — cutover de Excel manual a sistema MT Pricing

---

## 1. Prerequisitos de cutover

Antes de ejecutar el cutover, verificar:

- [ ] Training Log (`docs/training-log.md`) completado y firmado por Backup Operator
- [ ] Parallel-run sin discrepancias críticas durante ≥ 5 días hábiles
- [ ] Backup DB pre-cutover generado y verificado (ver §3)
- [ ] Excel `stock_dubai_v23_ARCHIVE_YYYY-MM-DD` archivado como read-only
- [ ] Sign-off de Sponsor + Champion + TI Integración

---

## 2. Procedimiento de cutover

### Fase 1: Go/No-Go (Día C-1)

1. Revisar último diff report `parallel-run-diff-YYYY-MM-DD.csv` — sin líneas críticas.
2. Confirmar disponibilidad del Backup Operator para la ventana de cutover.
3. Notificar a todos los stakeholders (Sponsor, Gerente, TI Integración).
4. Confirmar acceso admin a Supabase y Docker Compose.

### Fase 2: Freeze y backup (Día C, T+0)

```bash
# Generar dump de DB pre-cutover
PGPASSWORD=$POSTGRES_PASSWORD pg_dump \
  -h localhost -U postgres mt_pricing \
  -f backups/pre-cutover-$(date +%Y%m%d-%H%M%S).sql

# Archivar Excel como read-only
# (copiar a Supabase Storage bucket price-reference-excel/archive/)
```

### Fase 3: Activación sistema MT Pricing (Día C, T+1h)

```bash
# Reiniciar servicios con configuración de producción
docker-compose -f docker-compose.dev.yml up -d

# Verificar estado
docker-compose -f docker-compose.dev.yml ps
curl http://localhost:8000/health
```

---

## Rollback Playbook

> **NFR-16**: El rollback debe completarse en < 4 horas desde la decisión.

### Criterios para activar rollback

Activar rollback si se cumplen ≥ 1 de estas condiciones dentro de las primeras 72h post-cutover:

1. Tasa de error API > 5% sostenida > 10 minutos
2. Precios incorrectos publicados en canal externo
3. Pérdida de datos de aprobación no recuperable
4. Sistema inaccesible > 30 minutos sin ETA de resolución

### Pre-condiciones

- [ ] Backup DB disponible (verificar en `backups/` o Supabase backups)
- [ ] Excel `stock_dubai_v23_ARCHIVE_YYYY-MM-DD` accesible (read-only)
- [ ] Acceso admin a Supabase y Docker Compose confirmado

### Pasos de rollback

#### Fase 1: Notificación (0–15 min)

1. Notificar a psierra (Champion) + Gerente + TI Integración.
2. Crear incidente en registro de incidentes.
3. Confirmar decisión go/no-go rollback con Sponsor.

#### Fase 2: Freeze del sistema (15–30 min)

```bash
# Detener workers y frontend para evitar más escrituras
docker-compose -f docker-compose.dev.yml stop mt-pricing-worker mt-pricing-frontend

# Verificar que los contenedores están detenidos
docker-compose -f docker-compose.dev.yml ps
```

#### Fase 3: Backup del estado actual (30–60 min)

```bash
# Dump de la DB actual antes de restaurar
PGPASSWORD=$POSTGRES_PASSWORD pg_dump \
  -h localhost -U postgres mt_pricing \
  -f backups/pre-rollback-$(date +%Y%m%d-%H%M%S).sql
```

#### Fase 4: Restaurar DB desde backup (60–120 min)

```bash
# Restaurar backup pre-cutover (identificar el correcto en backups/)
# Timestamp del backup: YYYY-MM-DD HH:MM UTC (debe ser el día previo al cutover)
PGPASSWORD=$POSTGRES_PASSWORD psql \
  -h localhost -U postgres mt_pricing \
  -f backups/pre-cutover-YYYY-MM-DD.sql
```

#### Fase 5: Verificación (120–180 min)

- [ ] API responde: `curl http://localhost:8000/health`
- [ ] Login funciona en `http://localhost:3000`
- [ ] Precios visibles en dashboard: al menos 10 productos
- [ ] Excel `stock_dubai_v23_ARCHIVE` accesible y sin modificaciones

#### Fase 6: Notificación de resolución (180–240 min)

- [ ] Informar a todos los stakeholders del resultado
- [ ] Registrar en `docs/drill-log.md` con outcome
- [ ] Planificar análisis post-mortem

---

### Verificación Excel 90 días

El Excel `stock_dubai_v23_ARCHIVE_YYYY-MM-DD` debe estar disponible como read-only durante al menos 90 días post-cutover. Almacenado en:

- Supabase Storage bucket `price-reference-excel/archive/`
- Backup local en `MT_Pricing_Run_Kit/archive/` (read-only)

Para verificar disponibilidad:

```bash
# Verificar acceso vía API
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/exports/reference-excel/status
```

---

## Referencias

- Handbook operativo: [`docs/handbook-es.md`](../handbook-es.md)
- DR general: [`docs/runbooks/disaster-recovery.md`](./disaster-recovery.md)
- Drill log: [`docs/drill-log.md`](../drill-log.md)
- Training log: [`docs/training-log.md`](../training-log.md)

---

*Generado: 2026-05-12 — Sprint 8 — US-1B-05-04*
