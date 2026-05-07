# ADR-034: Despliegue Hetzner + Docker Compose prod

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-001 (parcial — capa despliegue)

## Contexto

El proyecto MT Middle East es **single-tenant** (ADR-014), interno (3-10 usuarios concurrentes Fase 1, 224 SKUs hoy → 5k-50k SKUs visión 2-3 años). No requiere auto-scaling agresivo. Sí requiere:

- Costo controlado (no Vercel pricing por usuario).
- Control sobre el host (logs, backups, cron, deploys atómicos).
- Alineamiento con la arquitectura de referencia BR Innovation `hppt-iom`.

## Decisión

**Despliegue en Hetzner + Docker Compose prod** (alineado con hppt-iom — a verificar contra el repo de referencia).

| Aspecto | Decisión |
|---------|----------|
| Servidor staging | Hetzner Cloud CX/CCX (4-8 vCPU, 16-32 GB RAM); Frankfurt o Helsinki por defecto (UAE-equivalente si TI MT exige residencia) |
| Servidor prod | Hetzner dedicated o Cloud CCX (8-16 vCPU, 32-64 GB RAM) |
| Orquestación | `docker-compose.prod.yml` con servicios: `caddy`, `frontend`, `backend`, `worker`, `worker-beat`, `redis` |
| Postgres + Auth + Storage | Supabase managed (fuera del compose; ADR-031, ADR-032, ADR-033) |
| Reverse proxy | Caddy (ADR-035) — TLS automático Let's Encrypt |
| Deploy | Scripts `scripts/deploy.sh` SSH al server: pull images de GHCR + `alembic upgrade` + `supabase db push` + `docker compose up -d` |
| CI/CD | GitHub Actions construye imágenes y pushea a GHCR; deploy step SSH al server con clave dedicada |
| Entornos | `dev` (Docker local), `staging` (Hetzner staging), `prod` (Hetzner prod) |
| Backups | Supabase WAL streaming (PITR managed) + dumps lógicos diarios cifrados a Supabase Storage / S3 externo |
| Monitoreo server | Hetzner monitoring + node_exporter scraped por Prometheus / Better Stack |

## Alternativas evaluadas

- **Vercel + Railway + Supabase**: managed y rápido, pero costo escala con tráfico/usuarios; Vercel + worker process Python no encaja directo (Vercel es serverless edge).
- **AWS ECS / EKS**: enterprise-grade; over-engineered para single-tenant 3-10 usuarios; costo más alto; pesa Fase 1.
- **Fly.io**: viable, pero Hetzner alineado con stack BR estándar y el costo es claramente menor.
- **DigitalOcean Droplets / Linode**: equivalentes a Hetzner; Hetzner ofrece mejor relación €/recursos en EU.

## Consecuencias positivas

- **Costo controlado** (Hetzner ~$40-200/mes por server vs Vercel/AWS).
- **Control total del host** (logs, backups, cron, deploys atómicos).
- **Docker Compose** = misma topología en dev/staging/prod (pequeñas diferencias).
- **Alineado con hppt-iom** → reuso de scripts, plantillas, runbook.
- **No serverless** → estados in-process (cache, conexiones DB pool) más simples.

## Consecuencias negativas / riesgos

- **Single host = SPOF** Fase 1 → mitigación: backups + scripts de re-provisioning + monitoring 24/7.
- **Operación manual** (parches OS, certs renew via Caddy automático, log rotation) → alinear con runbook hppt-iom.
- **Residencia UAE** (ADR-020 open): Hetzner no tiene presencia UAE; si TI MT exige UAE, evaluar provider local.
- **Sin auto-scaling**: si la carga crece más allá del server, hay que vertical scale o introducir LB con réplicas.

## Cuándo revisar

- **S0 — gating**: TI MT firma despliegue.
- Si single host falla > X veces, evaluar mover a réplicas + LB.
- Si residencia UAE se vuelve hard requirement: evaluar provider local.
- Cuando catálogo > 50k SKUs o usuarios > 100, considerar separar Redis y workers en host dedicado.
