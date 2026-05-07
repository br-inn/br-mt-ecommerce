---
adr: "ADR-050"
title: "IaC con Terraform y Hetzner provider"
status: "proposed"
date: "2026-05-06"
deciders: ["Pablo BR"]
related: ["ADR-020", "ADR-034", "ADR-035"]
supersedes: []
project: "mt-pricing-mdm-phase1"
---

# ADR-050 — IaC con Terraform y Hetzner provider

## Contexto

MT Middle East Fase 1 corre en **Hetzner Cloud** (ADR-020 cloud residencia EU + ADR-034 deploy Hetzner Docker Compose). Necesita 3 environments: dev, staging, prod, cada uno con servidores app/worker, volumes Postgres/Redis, network privada, firewalls, DNS.

Antecedente negativo: en proyectos previos BR Innovation se aprovisionó infra **manualmente vía Hetzner Console**, lo cual:
- No es reproducible.
- No tiene historial de cambios.
- DR lento (re-crear servers a mano cuesta horas).
- Prone a clicks-de-más (firewall mal configurado, volume sin attach, etc.).

Para MT Fase 1 (proyecto facturado a cliente externo + DR drill obligatorio S5) necesitamos IaC desde día 1.

## Decisión

Adoptamos **Terraform 1.7+** con provider `hetznercloud/hcloud` v1.45+ como herramienta única de Infrastructure-as-Code para Hetzner.

Para configuration management on-server (post-bootstrap) usamos **Ansible** (idempotente, copia configs, levanta containers).

Estructura repo en `infra/terraform/`:
- `modules/` — server, firewall, network, dns, volume, backups.
- `envs/` — dev, staging, prod (cada uno con su `terraform.tfvars` y `backend.tf`).
- `shared/` — providers, versions.

State backend: **Hetzner Object Storage** (S3-compatible, GA), bucket por env, encryption + versioning ON. Fallback a Terraform Cloud free tier si locking falla.

Bootstrapping flow:
1. `terraform apply` crea recursos cloud.
2. `cloud-init` instala docker + caddy + doppler-cli en server.
3. `ansible-playbook bootstrap.yaml` copia configs + arma compose.
4. `ansible-playbook deploy.yaml` levanta containers con secrets via Doppler.
5. Health check.

CI: GitHub Actions con OIDC (sin secrets de larga duración) ejecuta `terraform plan` en PR y `terraform apply` en merge to main (con manual approval para prod).

## Alternativas consideradas

### A. Pulumi (TypeScript)
- ✅ Lenguaje familiar para devs frontend.
- ✅ Loops, condicionales, abstracciones más naturales que HCL.
- ❌ Hetzner provider Pulumi (basado en TF) menos pulido — wrapper imperfecto.
- ❌ Mezcla código de app con código de infra (riesgo de errores).
- ❌ Runtime Node.js requerido en CI (más overhead).
- ❌ Comunidad Hetzner significativamente más pequeña que TF.
- **Rechazado**: TF es estándar de facto en Hetzner.

### B. Solo Ansible (sin Terraform)
- ✅ Una sola tool.
- ❌ Ansible no es declarativo para cloud resources — `hetzner_cloud_*` modules son second-class y incompletos.
- ❌ State management ausente (Ansible no recuerda qué creó).
- ❌ Drift detection ausente.
- **Rechazado**: provisioning declarativo es requisito.

### C. Crossplane / Argo / GitOps puro
- ✅ Bonito en clusters K8s.
- ❌ MT no usa K8s (ADR-034: Docker Compose).
- ❌ Overhead operacional desproporcionado.
- **Rechazado**: stack no compatible.

### D. Provisioning manual en Console + scripts bash
- ❌ Anti-pattern observado, fuente de problemas.
- **Rechazado**: explícitamente lo que queremos evitar.

### E. Hetzner Cloud API directo desde Python/scripts
- ✅ Flexible.
- ❌ Reinventar la rueda (state, locking, plan/apply, drift).
- ❌ Mantenimiento eterno.
- **Rechazado**: TF resuelve todo esto.

## Consecuencias

### Positivas
- Infra 100 % reproducible desde commit.
- DR drill posible (<30 min target).
- Plan diffs visibles en PRs (review-friendly).
- Versioning del state file → rollback infra posible.
- Equipo aprende standard tooling (Terraform es transferible).
- Costo herramienta: 0 EUR (Terraform OSS, Hetzner OS para state ~2.50 EUR/mes).

### Negativas
- **Curva aprendizaje** HCL para devs sin experiencia previa.
- **Doble tool** (Terraform + Ansible) — mental split provisioning vs. config.
- **State backend ops** (encryption, versioning, lock) requiere disciplina.
- **PR overhead** — cambios infra requieren review explícito.

### Mitigaciones
- Workshop 4h en S0 sobre Terraform + Hetzner provider.
- Templates / módulos pre-construidos para reducir boilerplate por env.
- Runbook DR + DR drill en S5 valida que el sistema funciona.
- `terraform fmt` + `tflint` + `tfsec` en pre-commit y CI.

## Costos estimados

| Recurso | EUR/mes |
|---|---|
| Hetzner servers (3 envs) | ~35 |
| Volumes + backups | ~12 |
| Floating IP + Object Storage | ~4 |
| **Total infra** | **~51** |
| Terraform Cloud (free tier ≤5 users) | 0 |
| **TOTAL** | **~51** |

## Definition of Done

- [ ] Repo `infra/terraform/` con módulos + 3 envs.
- [ ] State backend Hetzner OS configurado, encryption + versioning ON.
- [ ] CI GH Actions con OIDC: plan en PR, apply en merge.
- [ ] Module `server` con cloud-init que instala docker + caddy + doppler.
- [ ] Ansible playbooks `bootstrap.yaml` + `deploy.yaml`.
- [ ] DR drill ejecutado y documentado en S5 con tiempo < 30 min.
- [ ] `tfsec` + `tflint` passing en CI.
- [ ] Runbooks `dr-drill.md`, `add-new-env.md`, `rotate-server.md`.

## Referencias

- ADR-020: Cloud residencia UAE/EU (Hetzner Falkenstein como referencia).
- ADR-034: Deploy Hetzner Docker Compose.
- ADR-035: Reverse proxy Caddy.
- ADR-051: Secrets management con Doppler (provee `HCLOUD_TOKEN`).
- Documento: `_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md` §2.
- Terraform Hetzner provider: https://registry.terraform.io/providers/hetznercloud/hcloud
- Hetzner Object Storage: https://docs.hetzner.com/storage/object-storage/
