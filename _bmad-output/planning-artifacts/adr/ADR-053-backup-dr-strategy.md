# ADR-053: Estrategia de Backups + Disaster Recovery — MT Middle East Fase 1

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), TI MT, Paula (validador técnico)
- Related: ADR-019 (observabilidad), ADR-031 (Supabase Postgres), ADR-033 (Supabase Storage), ADR-034 (Hetzner + Docker Compose), ADR-017 (secretos Doppler), ADR-046 (Celery Beat DB scheduler), ADR-007 (audit trail)
- Supersedes / amplía: introduce capa de DR ausente en arquitectura previa.

## Contexto

Fase 1 es **single-server Hetzner + Supabase + Redis + Caddy** (3 usuarios internos MT, no SaaS, no 24/7). El stock está en `stock_dubai_v23` y costos en archivos sueltos: si la plataforma cae sin backup limpio, MT vuelve a Excel un viernes y pierde semanas de aprobaciones, FX as-of, decisiones de pricing y trazabilidad VAT UAE 2026.

Compliance VAT UAE 2026 exige **retención auditable de 5 años**. Audit trail vive en Postgres (ADR-007) y se replica en Better Stack como secundario (ADR-019), pero sin estrategia de backup formal el primario está expuesto a:

1. Hardware fail Hetzner Frankfurt (probabilidad baja, impacto alto).
2. Region outage Hetzner (probabilidad muy baja, impacto crítico).
3. Bug lógico del propio sistema que borra datos (mass delete, migration mal aplicada).
4. Supabase compromise / outage (depend en SLA del vendor; pasamos a degraded mode).
5. Account compromise (credencial Supabase / Hetzner robada → ransomware).
6. Borrado humano accidental (operador MT que ejecuta SQL en consola).

Necesitamos: **3-2-1 backup rule** (3 copias, 2 medios distintos, 1 off-site / off-provider), RTO/RPO declarados y firmados, runbooks ejecutables por on-call recién despierto, DR drill anual.

## Decisión

Adoptar la siguiente **estrategia 3-2-1 cross-provider** con Supabase como primario, Cloudflare R2 como off-provider y Backblaze B2 como cold archive para audit VAT UAE.

### 1. Postgres (source of truth)

| Capa | Mecanismo | Retención | RPO efectivo |
|------|-----------|-----------|--------------|
| L1 | **Supabase PITR** (plan tier ≥ Pro) | 7 días continuo | < 5 min |
| L2 | `pg_dump --format=custom` diario → R2 (cifrado age) | 7 daily + 4 weekly + 12 monthly + **7 yearly** | 24 h |
| L3 | Réplica del dump diario a B2 (cold) | igual que L2 | 24 h |

- Schedule: 02:00 GST diario via task Celery `backup_postgres_daily` (registrado en `job_definitions`, ADR-046).
- Cifrado at-rest: **age** (asymmetric, key rotada anual, llave privada custodia BR + MT).
- Validation: **weekly restore-test** automático a entorno staging temporal Hetzner (`backup_verify_weekly`).
- Yearly snapshot inmutable (Object Lock R2) para VAT UAE 2026 (5 años).

### 2. Supabase Storage

- Backup diario task `backup_storage_daily` sólo de buckets críticos: `master/` (imágenes producto) y `product-datasheets/`.
- Resto (`exports/`, `import-batches/`, thumbnails) se regenera; se acepta pérdida.
- Destino: R2 + B2 Glacier-class.
- Retención: 30 días + diff snapshots semanales 12 meses.

### 3. Redis

- **No source of truth.** Cache + queue.
- Tasks Celery idempotentes con retry exponencial (ya en ADR-030).
- `job_definitions` (ADR-046) está en Postgres → cubre L1/L2/L3.
- Aceptar pérdida en restart. Sin backup formal.

### 4. Application config / secretos

- IaC en Git (`docker-compose.prod.yml`, `Caddyfile`, Alembic migrations, Supabase migrations) → re-create infra desde repo en < 30 min.
- Doppler: snapshot semanal read-only de secrets cifrado con SOPS + age → rama `secrets-snapshot/` privada del repo (offline fallback).

### 5. Backup orchestration

Task `backup_daily` (orquestador) con sub-tasks fan-out:
1. `backup_postgres` → R2 + B2.
2. `backup_storage` (master + datasheets) → R2 + B2.
3. `backup_secrets_snapshot` (semanal) → repo SOPS.
4. `verify_backups_integrity` (checksum SHA-256, list objects, restore smoke test 1 tabla random).

Notification: éxito → Slack `#mt-ops`. Fallo → on-call alert (Better Stack on-call SEV2).

### 6. RTO / RPO Fase 1 (firmado)

| Concepto | Target Fase 1 | Target Fase 3 |
|----------|---------------|---------------|
| RTO global | **4 h** | 1 h |
| RPO global | **1 h** | 15 min |
| SLA disponibilidad horario laboral GCC (08:00–18:00 GST L–V) | **99.5 %** | 99.9 % |
| SLA fuera de horario | best-effort | 99.5 % |

Justificación Fase 1: 3 usuarios internos MT, no customer-facing, no 24/7. Tradeoff coste/cobertura razonable.

### 7. Coste mensual estimado backup cross-region (Fase 1, 224 SKUs → 50k SKUs proyectado)

| Concepto | Volumen Fase 1 | Coste/mes |
|----------|----------------|-----------|
| R2 storage (Postgres + master images, ~20 GB) | 20 GB | ~$0.30 |
| R2 egress (restore-test weekly, ~5 GB) | 5 GB | $0 (egress free) |
| B2 cold (Glacier-class, ~30 GB acumulado) | 30 GB | ~$0.18 |
| B2 egress drill anual | 30 GB | ~$0.30 |
| Class A/B operations (PUT/GET) | ~10k/mes | ~$0.05 |
| Supabase PITR (incluido en plan Pro $25/mes) | — | $0 marginal |
| **Total backup infra Fase 1** | — | **~$1–2/mes** + plan Supabase Pro ($25) |

Proyección Fase 3 (50k SKUs + 100 GB storage): ~$15–25/mes.

## Alternativas evaluadas

### A. Sólo Supabase PITR sin off-provider
- Pros: cero coste extra, gestionado.
- Contras: viola 3-2-1 (single vendor). Si Supabase comprometido o cuenta perdida → cero recuperación. Inaceptable VAT UAE 5 años.
- **Veredicto**: descartada.

### B. Backup mismo Hetzner volume snapshot
- Pros: barato (~$1/mes).
- Contras: mismo provider, mismo region. No cubre region outage ni account compromise.
- **Veredicto**: descartada como única solución; aceptable como L0 adicional.

### C. AWS S3 + Glacier en lugar de R2 + B2
- Pros: ecosistema maduro.
- Contras: egress caro ($0.09/GB) → drill anual y restore-tests cuestan ×30. R2 egress free es decisivo.
- **Veredicto**: descartada Fase 1.

### D. Replica Postgres self-hosted Hetzner (HA active-passive)
- Pros: RTO < 5 min.
- Contras: complejidad ops + coste server adicional. Innecesario Fase 1 single-tenant interno.
- **Veredicto**: diferida a Fase 2-3.

### E. Backups diarios sin verify automático
- Pros: simple.
- Contras: backup que no se restaura no existe. Industria estándar = verify weekly mínimo.
- **Veredicto**: descartada.

## Consecuencias positivas

- Cumple 3-2-1 cross-provider.
- Cumple retención VAT UAE 5 años (yearly snapshots inmutables R2 Object Lock).
- RTO/RPO realistas y firmados con MT.
- Verify weekly evita "backup zombie".
- Coste marginal ($1–2/mes Fase 1).

## Consecuencias negativas / riesgos

- Operacional: añade task Celery más + monitorización. Mitigado con `verify_backups_integrity`.
- Cifrado age: si llave privada se pierde, backups inrecuperables. Custodia dual BR + MT con vault físico.
- Restore-test consume slot Hetzner staging temporal weekly.

## Cuándo revisar

- **Cierre Fase 1a**: validar RTO/RPO en primer DR drill.
- **Cierre Fase 1b**: revisar volumen backup vs proyección.
- **Pre-Fase 3**: subir a HA active-passive (RTO 1 h, RPO 15 min).
