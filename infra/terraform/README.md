# Terraform — MT Pricing infra (US-1A-IAC-01)

Onboarding TI MT — provisión Hetzner + Cloudflare + Sentry + Better Stack via IaC.

---

## 1. Pre-requisitos

| Tool | Versión mínima | Install |
|------|---------------|---------|
| Terraform | >= 1.7.0, < 2.0 | https://developer.hashicorp.com/terraform/install |
| Doppler CLI | >= 3.66 | https://docs.doppler.com/docs/install-cli |
| `hcloud` CLI (opcional) | >= 1.40 | https://github.com/hetznercloud/cli |
| `jq` | >= 1.6 | brew/apt |

## 2. Secrets / tokens necesarios (en Doppler workspace `mt-pricing`)

| Secret | Scope | Quién lo emite |
|--------|-------|----------------|
| `HCLOUD_TOKEN` | full | TI MT (Hetzner project member) |
| `CLOUDFLARE_API_TOKEN` | DNS edit zone `mt-me.ae` | TI MT |
| `CLOUDFLARE_ZONE_ID` | read | TI MT |
| `SENTRY_AUTH_TOKEN` | `project:write,team:read` | DevOps BR + TI MT |
| `BETTER_STACK_API_TOKEN` | full | DevOps BR |
| `DOPPLER_TOKEN` | read-only service token (para data sources opt-in) | Doppler admin |

## 3. Bootstrap inicial

```bash
# 1) Doppler workspace
./infra/scripts/doppler-bootstrap.sh

# 2) Auth providers (puede correrlo ya envuelto por doppler run abajo)
export TF_VAR_hcloud_token=$(doppler secrets get HCLOUD_TOKEN --plain --project mt-pricing --config staging)
export TF_VAR_cloudflare_api_token=$(doppler secrets get CLOUDFLARE_API_TOKEN --plain --project mt-pricing --config staging)

# 3) Init (NO corras esto en Sprint 5 todavía — Hetzner project pendiente)
cd infra/terraform
terraform init
terraform validate
```

## 4. Plan + apply

**Sprint 5 — solo `validate`. NO `apply`.**

```bash
# Validate sintaxis + provider compat
terraform validate

# Cuando Hetzner project + Doppler workspace estén listos:
doppler run --project mt-pricing --config staging -- terraform plan -out=tfplan
doppler run --project mt-pricing --config staging -- terraform apply tfplan
```

## 5. Remote state

Estado local por defecto en Sprint 5. Para Sprint 6 movemos a Backblaze B2 EU
(s3-compatible) — descomentar bloque `backend "remote"` en `versions.tf`.

```hcl
# versions.tf — activar cuando Backblaze bucket exista
terraform {
  backend "s3" {
    bucket   = "mt-pricing-tfstate"
    key      = "staging.tfstate"
    region   = "eu-central-003"
    endpoint = "https://s3.eu-central-003.backblazeb2.com"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

## 6. Topología provisionada (US-1A-IAC-01)

| Recurso | Especificación | Coste mensual estimado |
|---------|----------------|------------------------|
| `hcloud_server.app` | CX22 (2 vCPU, 4GB RAM) | ~5.83 EUR |
| `hcloud_server.worker` | CX22 (2 vCPU, 4GB RAM) | ~5.83 EUR |
| `hcloud_server.db_bouncer` | CX11 (1 vCPU, 2GB RAM) | ~3.29 EUR |
| `hcloud_floating_ip.app` | IPv4 | ~1.00 EUR |
| `hcloud_network.main` | privada 10.0.0.0/16 | gratis |
| Storage Box BX11 | 1TB | ~3.50 EUR |
| **Total infra Hetzner** | | **~19.45 EUR/mes** |

Sentry SaaS + Better Stack tier paid se gestiona aparte.

## 7. Operaciones comunes

### Rotar SSH key

```bash
# Editar var.ssh_public_keys en tfvars (o env TF_VAR_ssh_public_keys)
terraform plan
terraform apply
```

### Reemplazar app server (canary deploy)

```bash
terraform taint 'hcloud_server.app'
terraform apply
# Floating IP se re-asigna automáticamente al nuevo server.
```

### Rollback infra

```bash
terraform state list
terraform state rm 'broken_resource'  # último recurso
# O restaurar desde state remoto previo (versioned bucket)
```

## 8. Bloqueos conocidos S5

- Hetzner project + servers pendientes de provisión TI MT.
- Doppler workspace `mt-pricing` pendiente de seedeo de secrets.
- Sentry org `mt-middle-east` pendiente de creación + auth token.
- Better Stack team pendiente.

Apply real diferido a Sprint 6 una vez TI MT cierre dependencias (a)–(g) del
sprint5-backlog §1.

## 9. Referencias

- Sprint 5 backlog: `_bmad-output/planning-artifacts/sprint5-backlog-refined.md`
- ADR-050: Terraform on Hetzner Cloud
- ADR-051: Doppler secrets vault + key custodia
- ADR-077: Observability operating runbook
- ADR-078: IaC + secrets management strategy
