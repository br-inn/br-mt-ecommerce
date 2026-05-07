---
title: "Diseño de Migration Discipline + IaC + Secrets — MT Middle East Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
related: ["architecture-mt-pricing-mdm-phase1.md", "ADR-045", "ADR-046"]
adrs_propuestos: ["ADR-049", "ADR-050", "ADR-051"]
---

# Diseño de Migration Discipline + IaC + Secrets — MT Middle East Fase 1

## 0. Resumen ejecutivo

Este documento define las **disciplinas operativas no-negociables** para que MT Middle East Fase 1 sea producción-grade desde día 1, evitando los anti-patterns observados en `hppt-iom-review_1` (solo 21 migraciones versionadas, schema gestionado parcialmente desde Supabase Studio sin commit, infra creada manualmente, secretos en `.env` locales).

Tres pilares:

1. **Migration discipline** — Todo cambio de schema versionado en Git, con split claro Alembic (`public.*`) ↔ Supabase migrations (`auth.*`, `storage.*`, RLS), expand-contract obligatorio, drift detector semanal en CI.
2. **IaC con Terraform** — Hetzner Cloud + DNS + Firewalls + Volumes 100 % declarativo, modules reutilizables, environments dev/staging/prod, state remoto encriptado, DR drill probado en S5.
3. **Secrets management con Doppler** — Single source of truth, inyección runtime via CLI, rotación trimestral, gitleaks pre-commit, SSO con Google Workspace.

**Stack final**: Alembic + Supabase CLI + Terraform 1.7 + hcloud provider + Doppler + gitleaks + GitHub Actions + pgTAP.

---

## 1. Migration Discipline

### 1.1 Split de responsabilidades

| Schema | Owner | Tooling | Repo path |
|---|---|---|---|
| `public.*` (tablas aplicativas, funciones, triggers, índices, constraints) | Backend dev | Alembic | `apps/backend/alembic/versions/` |
| `auth.*` (custom JWT claims, role hooks, triggers `on_auth_user_created`) | Backend / DevOps | Supabase CLI | `supabase/migrations/` |
| `storage.*` (buckets, policies) | Backend / DevOps | Supabase CLI | `supabase/migrations/` |
| RLS de `public.*` que usa `auth.uid()` / `auth.jwt()` | Backend / DevOps | Supabase CLI | `supabase/migrations/` |
| RLS de `public.*` que NO depende de `auth.*` (ej. tenant simple) | Backend dev | Alembic (raw SQL op) | `apps/backend/alembic/versions/` |
| Seeds (datos demo, lookups) | Backend dev | Script Python idempotente | `apps/backend/seeds/` |

**Regla**: una RLS policy se versiona donde vive el `auth.uid()` lookup. Si la policy hace `auth.uid() = user_id`, va a Supabase migrations (porque el rol `authenticated` y el contexto JWT son responsabilidad de Supabase). Si es solo un check de columna `tenant_id = current_setting('app.tenant_id')`, va a Alembic.

### 1.2 Convención naming pareado

Cuando una feature requiere ambas migraciones, comparten **prefijo timestamp + número de orden**:

```
apps/backend/alembic/versions/20260601_001_add_users_table.py
supabase/migrations/20260601_001_users_rls.sql
```

Esto permite a un dev `git log --grep="20260601_001"` y ver la feature completa.

### 1.3 Workflow end-to-end

```mermaid
flowchart TD
    A[Dev edita modelo SQLAlchemy<br/>en app/db/models/] --> B[alembic revision --autogenerate<br/>-m 'add users table']
    B --> C{Migración generada<br/>correcta?}
    C -->|No| D[Editar manualmente<br/>downgrade real, idempotencia]
    C -->|Sí| E[¿Requiere RLS / auth / storage?]
    D --> E
    E -->|Sí| F[Crear supabase/migrations/<br/>YYYYMMDD_NNN_feature.sql]
    E -->|No| G[Tests locales:<br/>alembic upgrade head<br/>+ alembic downgrade -1<br/>+ alembic upgrade head]
    F --> G
    G --> H[git commit + PR]
    H --> I[CI: lint + migrate-check]
    I --> J[CI: pgTAP tests RLS]
    J --> K[Merge to main]
    K --> L[Deploy staging:<br/>1 supabase db push<br/>2 alembic upgrade head]
    L --> M[Smoke tests staging]
    M --> N{Pasan?}
    N -->|No| O[Rollback staging:<br/>alembic downgrade -1]
    N -->|Sí| P[Aprobación manual]
    P --> Q[Deploy prod:<br/>dump pre-deploy<br/>+ migrate<br/>+ sanity]
    Q --> R{Sanity OK?}
    R -->|No| S[Rollback prod runbook]
    R -->|Sí| T[Done]
```

### 1.4 Expand-Contract pattern (regla de oro)

**Prohibido en una sola migración con código vivo que aún la usa**:
- `DROP TABLE`
- `DROP COLUMN`
- `RENAME COLUMN` (equivale a drop + add)
- `ALTER COLUMN ... NOT NULL` sin backfill previo
- `ALTER COLUMN ... TYPE` que no sea cast trivial

**Patrón obligatorio para cambios destructivos**:

```
Sprint N:
  Migración A (expand): ADD COLUMN new_col NULLABLE
  Deploy app vN: dual-write (escribe old_col + new_col)

Sprint N+1:
  Job Celery: backfill new_col desde old_col
  Verify: count(*) WHERE new_col IS NULL = 0
  Deploy app vN+1: dual-read (prefiere new_col, fallback old_col)

Sprint N+2:
  Deploy app vN+2: solo new_col
  Migración B (contract): DROP COLUMN old_col
```

Esto es **3 sprints mínimo** para un drop. No negociable en prod.

### 1.5 Reglas de idempotencia

```python
# apps/backend/alembic/versions/20260601_001_add_users_table.py
"""add users table

Revision ID: 20260601_001
Revises: 20260530_005
Create Date: 2026-06-01 09:15:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260601_001"
down_revision = "20260530_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mt_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="comercial"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('comercial', 'gerente', 'ti', 'admin')",
                           name="ck_mt_users_role_valid"),
        if_not_exists=True,  # idempotente
    )
    op.create_index("ix_mt_users_email", "mt_users", ["email"], if_not_exists=True)
    op.create_index("ix_mt_users_auth_user_id", "mt_users", ["auth_user_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_mt_users_auth_user_id", table_name="mt_users")
    op.drop_index("ix_mt_users_email", table_name="mt_users")
    op.drop_table("mt_users")
```

Y la counterpart Supabase:

```sql
-- supabase/migrations/20260601_001_users_rls.sql

-- enable RLS
ALTER TABLE public.mt_users ENABLE ROW LEVEL SECURITY;

-- policy: usuarios solo ven su propio registro
DROP POLICY IF EXISTS "mt_users_self_read" ON public.mt_users;
CREATE POLICY "mt_users_self_read"
  ON public.mt_users
  FOR SELECT
  TO authenticated
  USING (auth_user_id = auth.uid());

-- policy: solo admin escribe
DROP POLICY IF EXISTS "mt_users_admin_write" ON public.mt_users;
CREATE POLICY "mt_users_admin_write"
  ON public.mt_users
  FOR ALL
  TO authenticated
  USING ((auth.jwt() ->> 'role') = 'admin')
  WITH CHECK ((auth.jwt() ->> 'role') = 'admin');

-- DOWN script paralelo (Supabase CLI lo soporta como migration repair)
-- ROLLBACK: drop policies + disable RLS
-- DROP POLICY IF EXISTS "mt_users_admin_write" ON public.mt_users;
-- DROP POLICY IF EXISTS "mt_users_self_read" ON public.mt_users;
-- ALTER TABLE public.mt_users DISABLE ROW LEVEL SECURITY;
```

### 1.6 Migraciones de datos (separadas)

Las **data migrations** NO van en Alembic. Van en `apps/backend/app/db/data_migrations/` como tasks Celery con audit:

```python
# apps/backend/app/db/data_migrations/202606_backfill_user_roles.py
from app.workers.celery_app import celery_app
from app.db.session import async_session_factory
from app.models.audit import AuditLog
from sqlalchemy import text

@celery_app.task(name="data_migrations.backfill_user_roles", bind=True)
async def backfill_user_roles(self, dry_run: bool = True):
    async with async_session_factory() as db:
        # log start
        await db.execute(
            AuditLog.__table__.insert().values(
                action="data_migration.start",
                entity="mt_users",
                payload={"task_id": self.request.id, "dry_run": dry_run},
            )
        )
        result = await db.execute(
            text("UPDATE mt_users SET role = 'comercial' WHERE role IS NULL")
            if not dry_run else
            text("SELECT COUNT(*) FROM mt_users WHERE role IS NULL")
        )
        await db.execute(
            AuditLog.__table__.insert().values(
                action="data_migration.end",
                entity="mt_users",
                payload={"task_id": self.request.id, "rows_affected": result.rowcount},
            )
        )
        await db.commit()
```

Trigger: manual via management command, registrado en runbook, requiere aprobación de Pablo BR.

### 1.7 Rollback runbook

```yaml
# runbooks/rollback-migration.yaml
name: "Rollback de migración fallida en producción"
trigger: "Smoke tests post-deploy fallan o errores 500 sostenidos"
prerequisites:
  - acceso SSH al server de prod
  - dump pre-deploy disponible en object storage
  - confirmación verbal de Pablo BR
steps:
  - id: 1
    action: "Revertir versión de aplicación"
    cmd: |
      cd /opt/mt && \
      docker compose pull mt-backend:vN-1 && \
      docker compose up -d mt-backend
  - id: 2
    action: "Rollback Alembic"
    cmd: "docker compose exec mt-backend alembic downgrade -1"
  - id: 3
    action: "Rollback Supabase migration (si aplicó)"
    cmd: "supabase migration repair --status reverted <version>"
  - id: 4
    action: "Verificar health"
    cmd: "curl -f https://api.mt.brinnovation.app/health"
  - id: 5
    action: "Si falla, restore desde dump"
    cmd: "psql $DATABASE_URL < /backups/pre-deploy-YYYYMMDD-HHMM.sql"
post:
  - notificar #mt-ops Slack
  - postmortem en 24h
```

### 1.8 Testing de migraciones en CI

```yaml
# .github/workflows/migrate-check.yml
name: migrate-check
on: [pull_request]

jobs:
  migrate-roundtrip:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: supabase/setup-cli@v1
        with: { version: latest }
      - run: pip install -r apps/backend/requirements.txt
      - name: Apply Supabase migrations
        run: supabase db push --db-url "$DATABASE_URL"
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/postgres
      - name: Apply Alembic migrations
        working-directory: apps/backend
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/postgres
      - name: Roundtrip — downgrade all
        working-directory: apps/backend
        run: alembic downgrade base
      - name: Re-upgrade
        working-directory: apps/backend
        run: alembic upgrade head
      - name: pgTAP tests RLS
        run: pg_prove -d "$DATABASE_URL" tests/pgtap/*.sql
```

### 1.9 Drift detector

```yaml
# .github/workflows/drift-detect.yml
name: drift-detect
on:
  schedule:
    - cron: '0 6 * * 1'  # lunes 6am UTC
  workflow_dispatch:

jobs:
  detect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Dump prod schema
        run: |
          pg_dump --schema-only --no-owner --no-privileges \
            "$PROD_DATABASE_URL" > /tmp/prod-schema.sql
      - name: Apply migrations to clean DB and dump
        run: |
          docker run -d --name pg -p 5433:5432 -e POSTGRES_PASSWORD=test postgres:16
          sleep 5
          # apply supabase + alembic
          # ... (similar a migrate-check)
          pg_dump --schema-only --no-owner --no-privileges \
            postgresql://postgres:test@localhost:5433/postgres > /tmp/expected-schema.sql
      - name: Diff
        run: |
          if ! diff -u /tmp/expected-schema.sql /tmp/prod-schema.sql > /tmp/drift.diff; then
            echo "DRIFT DETECTED"
            cat /tmp/drift.diff
            curl -X POST $SLACK_WEBHOOK -d "{\"text\":\"Schema drift detected en MT prod\"}"
            exit 1
          fi
        env:
          PROD_DATABASE_URL: ${{ secrets.PROD_DATABASE_URL_RO }}
          SLACK_WEBHOOK: ${{ secrets.SLACK_OPS_WEBHOOK }}
```

### 1.10 Estimación esfuerzo

EP-1A-12 Migration discipline — **13 SP**:
- ST-1A-12-01 Setup Alembic + 1ª migration users (3 SP)
- ST-1A-12-02 Setup Supabase CLI + 1ª migration RLS (2 SP)
- ST-1A-12-03 pgTAP setup + 5 tests RLS (3 SP)
- ST-1A-12-04 CI gate migrate-check (2 SP)
- ST-1A-12-05 Drift detector weekly (2 SP)
- ST-1A-12-06 Docs expand-contract + rollback runbook (1 SP)

---

## 2. IaC para Hetzner

### 2.1 Tooling: Terraform + hcloud provider

**Recomendación: Terraform 1.7+ con provider `hetznercloud/hcloud` v1.45+**.

Justificación:
- **Provider Hetzner oficial maduro** (v1.45+, soporta todos los recursos: servers, volumes, networks, firewalls, floating IPs, load balancers, certificates).
- **HCL más declarativo** que Pulumi/TS para infra; menor superficie de bugs vs. lenguaje imperativo.
- **Comunidad y docs** abundantes (Terraform >>> Pulumi en Hetzner).
- **State remote** soportado out-of-the-box.
- **No tiene runtime dependency** (binario único, no Node.js como Pulumi).

Descartado:
- **Pulumi**: bonito pero mezcla código de app con infra; Hetzner provider menos pulido.
- **Ansible solo**: bueno para config management, no para provisioning declarativo de cloud resources (ansible.builtin.hetzner_cloud_* es second-class).

**Híbrido**: Terraform para provisioning + Ansible para post-bootstrap (instalar docker, copiar configs, levantar containers).

### 2.2 Recursos gestionados como código

| Recurso | Tipo TF | Cantidad estimada Fase 1 |
|---|---|---|
| Servidor app | `hcloud_server` (CX22 dev, CX42 staging, CCX13 prod) | 3 |
| Servidor worker | `hcloud_server` (CCX13 prod) | 1 |
| Volume Postgres | `hcloud_volume` (50 GB prod, 20 GB staging) | 2 |
| Volume backups | `hcloud_volume` (100 GB prod) | 1 |
| Network privada | `hcloud_network` + subnets | 1 por env |
| Firewall app | `hcloud_firewall` (22, 80, 443) | 1 por env |
| Firewall db (interno) | `hcloud_firewall` (5432, 6379 solo private) | 1 por env |
| Floating IP prod | `hcloud_floating_ip` | 1 |
| DNS records | `cloudflare_record` (Cloudflare como DNS) | ~10 |
| Object storage backups | `hcloud_object_storage_bucket` (cuando GA) o R2 | 1 |
| Snapshots automáticos | `hcloud_server` con `backups = true` | siempre prod |

### 2.3 Estructura repo

```
infra/
├── terraform/
│   ├── modules/
│   │   ├── server/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   └── cloud-init.yaml.tpl
│   │   ├── firewall/
│   │   ├── network/
│   │   ├── dns/
│   │   └── backups/
│   ├── envs/
│   │   ├── dev/
│   │   │   ├── main.tf
│   │   │   ├── terraform.tfvars
│   │   │   └── backend.tf
│   │   ├── staging/
│   │   └── prod/
│   └── shared/
│       ├── providers.tf
│       └── versions.tf
├── ansible/
│   ├── inventory/
│   │   ├── dev.yaml
│   │   ├── staging.yaml
│   │   └── prod.yaml
│   ├── playbooks/
│   │   ├── bootstrap.yaml
│   │   ├── deploy.yaml
│   │   └── backup-restore.yaml
│   └── roles/
│       ├── docker/
│       ├── caddy/
│       └── monitoring/
└── runbooks/
    ├── dr-drill.md
    ├── add-new-env.md
    └── rotate-server.md
```

### 2.4 Snippet módulo `server`

```hcl
# infra/terraform/modules/server/main.tf
terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
}

variable "name"          { type = string }
variable "server_type"   { type = string  default = "cx22" }
variable "location"      { type = string  default = "fsn1" }
variable "image"         { type = string  default = "ubuntu-24.04" }
variable "ssh_key_ids"   { type = list(number) }
variable "network_id"    { type = number }
variable "firewall_ids"  { type = list(number) }
variable "labels"        { type = map(string)  default = {} }
variable "user_data"     { type = string  default = "" }
variable "backups"       { type = bool    default = false }

resource "hcloud_server" "this" {
  name        = var.name
  server_type = var.server_type
  image       = var.image
  location    = var.location
  ssh_keys    = var.ssh_key_ids
  firewall_ids = var.firewall_ids
  backups     = var.backups
  user_data   = var.user_data
  labels      = merge(var.labels, { managed_by = "terraform", project = "mt" })

  network {
    network_id = var.network_id
  }

  lifecycle {
    ignore_changes = [user_data, image]  # evita recreate accidental por imagen actualizada
  }
}

resource "hcloud_server_network" "this" {
  server_id  = hcloud_server.this.id
  network_id = var.network_id
}

output "id"          { value = hcloud_server.this.id }
output "ipv4"        { value = hcloud_server.this.ipv4_address }
output "private_ip"  { value = one(hcloud_server.this.network[*].ip) }
```

### 2.5 Snippet env `prod`

```hcl
# infra/terraform/envs/prod/main.tf
terraform {
  required_version = ">= 1.7"
  backend "s3" {
    bucket                      = "mt-tf-state-prod"
    key                         = "prod/terraform.tfstate"
    endpoint                    = "https://fsn1.your-objectstorage.com"
    region                      = "us-east-1"  # placeholder, hcloud OS no usa
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
    encrypt                     = true
  }
}

provider "hcloud" {
  token = var.hcloud_token  # de Doppler / TF_VAR_hcloud_token
}

provider "cloudflare" {
  api_token = var.cloudflare_token
}

module "network" {
  source   = "../../modules/network"
  name     = "mt-prod-net"
  ip_range = "10.10.0.0/16"
}

module "firewall_app" {
  source = "../../modules/firewall"
  name   = "mt-prod-app-fw"
  rules = [
    { direction = "in", protocol = "tcp", port = "22",  source_ips = var.bastion_ips },
    { direction = "in", protocol = "tcp", port = "80",  source_ips = ["0.0.0.0/0", "::/0"] },
    { direction = "in", protocol = "tcp", port = "443", source_ips = ["0.0.0.0/0", "::/0"] },
  ]
}

module "server_app" {
  source        = "../../modules/server"
  name          = "mt-prod-app-01"
  server_type   = "ccx13"
  location      = "fsn1"
  ssh_key_ids   = [hcloud_ssh_key.devops.id]
  network_id    = module.network.id
  firewall_ids  = [module.firewall_app.id]
  backups       = true
  user_data     = file("${path.module}/cloud-init.yaml")
  labels        = { env = "prod", role = "app" }
}

module "volume_pg" {
  source    = "../../modules/volume"
  name      = "mt-prod-pg-data"
  size      = 50
  server_id = module.server_app.id
  format    = "ext4"
}

module "dns" {
  source     = "../../modules/dns"
  zone_id    = var.cloudflare_zone_id
  records = [
    { name = "api.mt",  type = "A", value = module.server_app.ipv4, ttl = 300 },
    { name = "app.mt",  type = "A", value = module.server_app.ipv4, ttl = 300 },
  ]
}
```

### 2.6 Bootstrapping flow

```mermaid
flowchart TD
    A[git push infra/terraform/envs/prod] --> B[CI: terraform fmt + validate + tflint]
    B --> C[CI: terraform plan PR comment]
    C --> D{Review + approve}
    D --> E[terraform apply<br/>via GH Actions con OIDC]
    E --> F[hcloud crea: server + volume + network + firewall + DNS]
    F --> G[Cloud-init en server:<br/>install docker + docker-compose + caddy + doppler-cli]
    G --> H[Ansible playbook bootstrap.yaml:<br/>copy compose files + .caddyfile]
    H --> I[Ansible playbook deploy.yaml:<br/>doppler run -- docker compose up -d]
    I --> J[Health check:<br/>curl https://api.mt.brinnovation.app/health]
    J --> K{200?}
    K -->|Sí| L[Done]
    K -->|No| M[Investigar logs + rollback TF si infra]
```

### 2.7 Snippet cloud-init

```yaml
# infra/terraform/modules/server/cloud-init.yaml.tpl
#cloud-config
package_update: true
package_upgrade: true
packages:
  - ca-certificates
  - curl
  - gnupg
  - ufw
  - fail2ban
runcmd:
  - install -m 0755 -d /etc/apt/keyrings
  - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  - echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  - apt-get update -y
  - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  - curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | sh
  - useradd -m -s /bin/bash mt && usermod -aG docker mt
  - mkdir -p /opt/mt && chown mt:mt /opt/mt
  - mkdir -p /mnt/pg-data
write_files:
  - path: /etc/sysctl.d/99-mt.conf
    content: |
      vm.overcommit_memory=1
      net.core.somaxconn=4096
  - path: /etc/docker/daemon.json
    content: |
      {
        "log-driver": "json-file",
        "log-opts": { "max-size": "100m", "max-file": "3" }
      }
```

### 2.8 State backend

- **Hetzner Object Storage** (S3-compatible, GA en 2024).
- Bucket por env: `mt-tf-state-dev`, `mt-tf-state-staging`, `mt-tf-state-prod`.
- **Server-side encryption** activado.
- **Versioning** activado (rollback de state si corruption).
- **Lock**: DynamoDB local replacement no necesario porque Hetzner OS soporta strong consistency (reciente). Si hay race conditions, fallback a Terraform Cloud free tier.

### 2.9 DR drill

Ejercicio obligatorio en S5 antes de production cutover:
1. Borrar env staging completo (`terraform destroy`).
2. Cronómetro on.
3. `terraform apply` desde cero.
4. `ansible-playbook bootstrap.yaml`.
5. Restaurar último dump Postgres desde object storage.
6. `ansible-playbook deploy.yaml`.
7. Health check.
8. Cronómetro off. **Target: < 30 min**. Si falla, iterar.

### 2.10 Costos infra

Estimación mensual EUR (Fase 1):

| Recurso | Cantidad | Precio unit/mes | Total |
|---|---|---|---|
| CCX13 prod app | 1 | 13.00 | 13.00 |
| CCX13 prod worker | 1 | 13.00 | 13.00 |
| CX22 staging | 1 | 4.50 | 4.50 |
| CX22 dev | 1 | 4.50 | 4.50 |
| Volume 50 GB prod | 1 | 2.20 | 2.20 |
| Volume 100 GB backups | 1 | 4.40 | 4.40 |
| Volume 20 GB staging | 1 | 0.88 | 0.88 |
| Backups automáticos prod | 2 | 20% del server | 5.20 |
| Object Storage state + dumps (~50GB) | 1 | 2.50 | 2.50 |
| Floating IP | 1 | 1.19 | 1.19 |
| **Total Hetzner** | | | **~51 EUR/mes** |
| Cloudflare (DNS free tier) | 1 | 0 | 0 |
| Terraform Cloud (free, hasta 5 users) | 1 | 0 | 0 |
| **GRAN TOTAL** | | | **~51 EUR/mes** |

### 2.11 Estimación esfuerzo

EP-1A-13 IaC Terraform — **21 SP**:
- ST-1A-13-01 Setup TF skeleton + state backend + provider auth (3 SP)
- ST-1A-13-02 Module server + cloud-init (3 SP)
- ST-1A-13-03 Module network + firewall (2 SP)
- ST-1A-13-04 Module DNS (Cloudflare) (2 SP)
- ST-1A-13-05 Module volume + backups (2 SP)
- ST-1A-13-06 Env dev + staging (3 SP)
- ST-1A-13-07 Env prod (2 SP)
- ST-1A-13-08 Ansible playbooks bootstrap + deploy (2 SP)
- ST-1A-13-09 Runbooks DR + DR drill primer (1 SP)
- ST-1A-13-10 GH Actions terraform plan/apply con OIDC (1 SP)

---

## 3. Secrets Management

### 3.1 Tooling: Doppler

**Recomendación: Doppler con plan Team**.

Justificación:
- **Alineado con stack BR Innovation** (Pablo confirmó uso en projects previos).
- **Managed**, sin self-hosting overhead vs. Vault.
- **CLI** maduro, integración nativa con Docker, K8s, CI providers.
- **SSO** Google Workspace / Microsoft Entra incluido en plan Team.
- **Audit log** built-in.
- **Rotación scheduled** para servicios soportados.
- **Fallback** secret refs (no requiere internet permanente en runtime gracias a cache).

Descartado:
- **HashiCorp Vault**: enterprise-grade pero overkill, requiere ops dedicada, self-host costoso.
- **1Password Secrets Automation**: bueno pero menos maduro en CLI/CI workflows.
- **GitHub Secrets + SOPS**: válido para arrancar pero no escala (sin audit, sin rotación, sin SSO).

### 3.2 Categorías + projects en Doppler

Estructura: 1 project Doppler por componente, configs por env.

```
mt-backend
├── dev_personal_pablo
├── dev
├── staging
└── prod

mt-frontend
├── dev
├── staging
└── prod

mt-worker
├── dev
├── staging
└── prod

mt-infra
├── dev
├── staging
└── prod
```

| Project | Secret | Categoría | Rotación |
|---|---|---|---|
| `mt-backend` | `DATABASE_URL` | App | Trimestral |
| `mt-backend` | `SUPABASE_SERVICE_ROLE_KEY` | App crítico | Trimestral |
| `mt-backend` | `SUPABASE_JWT_SECRET` | App crítico | Trimestral |
| `mt-backend` | `REDIS_URL` | App | Trimestral |
| `mt-backend` | `SENTRY_DSN` | App | Anual |
| `mt-backend` | `OPENAI_API_KEY` | App externo | Trimestral (manual) |
| `mt-backend` | `COHERE_API_KEY` | App externo | Trimestral (manual) |
| `mt-backend` | `BRIGHTDATA_USERNAME` / `BRIGHTDATA_PASSWORD` | App externo | Trimestral |
| `mt-backend` | `RESEND_API_KEY` | App externo | Anual |
| `mt-frontend` | `NEXT_PUBLIC_SUPABASE_URL` | Público | N/A |
| `mt-frontend` | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Público | Trimestral (junto con service_role) |
| `mt-frontend` | `NEXT_PUBLIC_SENTRY_DSN` | Público | Anual |
| `mt-infra` | `HCLOUD_TOKEN` | Infra | Trimestral |
| `mt-infra` | `CLOUDFLARE_API_TOKEN` | Infra | Trimestral |
| `mt-infra` | `SSH_DEPLOY_KEY` | Infra | Anual |
| CI | `DOPPLER_SERVICE_TOKEN_*` | CI | Trimestral |
| CI | `GITHUB_PAT` | CI | Trimestral |
| Ops | `SLACK_WEBHOOK_OPS` | Ops | Anual |

### 3.3 Inyección runtime

**Local dev**:
```bash
doppler login
doppler setup --project mt-backend --config dev_personal_pablo
doppler run -- uvicorn app.main:app --reload
```

**Docker prod (entrypoint)**:
```dockerfile
# apps/backend/Dockerfile
FROM python:3.12-slim
RUN curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | sh
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENTRYPOINT ["doppler", "run", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Y en `docker-compose.prod.yaml`:
```yaml
services:
  backend:
    image: ghcr.io/br-innovation/mt-backend:latest
    environment:
      DOPPLER_TOKEN: ${DOPPLER_TOKEN_BACKEND_PROD}
    # doppler run inyecta el resto de env vars en runtime
```

`DOPPLER_TOKEN_BACKEND_PROD` es un **service token scoped** a `mt-backend/prod`, read-only, almacenado en `/etc/mt/doppler.env` en el server (file 0600 owned by `mt`).

**CI**:
```yaml
# .github/workflows/deploy-prod.yml
- uses: dopplerhq/cli-action@v3
- run: doppler secrets download --no-file --format env > .env.ci
  env:
    DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN_CI_PROD }}
- run: docker compose --env-file .env.ci up -d
```

### 3.4 Rotación

**Política trimestral críticos** (hoja Notion + cron Slack reminder):
- Q1: Postgres password, Supabase service_role/JWT, Redis password.
- Q2: API keys externas (OpenAI, Cohere, Bright Data, Resend).
- Q3: SSH deploy keys, HCloud token, Cloudflare token.
- Q4: CI tokens, GitHub PAT.

**Mecanismo**:
1. Generar nuevo secret en provider (ej. Supabase: rotate JWT secret).
2. `doppler secrets set NEW_KEY=value --project mt-backend --config prod`.
3. Triggers webhook → redeploy app.
4. Validar health.
5. Revocar old secret en provider.
6. Audit log: Pablo añade entry en Notion `secrets-rotation-log.md` con fecha + quién + qué + ticket.

**Runbook** detallado en `runbooks/rotate-secret-<service>.md`.

### 3.5 Detección de leaks

**Pre-commit**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.0
    hooks:
      - id: gitleaks
```

**CI**:
```yaml
# .github/workflows/secret-scan.yml
name: secret-scan
on: [push, pull_request]
jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}
```

**GitHub native**:
- Push protection enabled en repo settings.
- Secret scanning alerts → email Pablo + Slack #mt-security.

**Sentry PII redaction**:
```python
# apps/backend/app/core/observability.py
import sentry_sdk

def before_send(event, hint):
    # redact common token patterns
    import re
    s = str(event)
    if re.search(r"(sk-[a-zA-Z0-9]{20,}|eyJ[A-Za-z0-9_-]{20,})", s):
        return None  # drop event entirely
    return event

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    before_send=before_send,
    send_default_pii=False,
)
```

### 3.6 Acceso humano

**Roles Doppler**:
- `admin`: Pablo BR (rotación, billing, SSO config).
- `developer`: TI integración MT (read prod, write dev/staging).
- `viewer`: nadie por defecto. Comercial / Gerente / Director NUNCA acceden a Doppler.

**SSO**: Google Workspace `*.brinnovation.com` (Pablo) + Microsoft Entra MT (TI integración) si MT lo configura.

**Audit log** revisado mensual por Pablo. Anomalías → security review.

### 3.7 Costos Doppler

| Plan | Precio | Aplica |
|---|---|---|
| Developer (free) | 0 USD | dev_personal hasta 5 users, sin SSO, audit limitado |
| Team | 7 USD/user/mes | Recomendado Fase 1 — 3 users (Pablo + 2 TI MT) = **~21 USD/mes** |
| Enterprise | custom | Si MT crece >10 users con compliance requirements |

**Total proyectado**: 21 USD/mes (~20 EUR/mes).

### 3.8 Estimación esfuerzo

EP-1A-14 Secrets management — **8 SP**:
- ST-1A-14-01 Setup Doppler workspace + projects + configs (2 SP)
- ST-1A-14-02 Integrate doppler CLI en Dockerfiles + compose (2 SP)
- ST-1A-14-03 GH Actions integration con service tokens (1 SP)
- ST-1A-14-04 gitleaks pre-commit + CI (1 SP)
- ST-1A-14-05 Rotation runbooks + Notion log template (1 SP)
- ST-1A-14-06 SSO setup + role assignment (1 SP)

---

## 4. Implementation plan consolidado

| Épica | SP | Sprint sugerido | Dependencias |
|---|---|---|---|
| EP-1A-14 Secrets management | 8 | S0 | Ninguna (primero, todo lo demás depende) |
| EP-1A-13 IaC Terraform | 21 | S0–S1 | EP-1A-14 (consume HCLOUD_TOKEN) |
| EP-1A-12 Migration discipline | 13 | S1 | EP-1A-13 (necesita DB en staging) |

**Total**: 42 SP — distribuible en S0 + S1 sin sobrecargar el sprint productivo.

### 4.1 Definition of Done global

- [ ] Doppler configurado con SSO + 3 projects + rotación documentada.
- [ ] gitleaks bloquea PRs con secrets.
- [ ] Terraform aplica dev + staging + prod from-scratch en < 30 min.
- [ ] State remoto encriptado en Hetzner OS.
- [ ] Alembic + Supabase CLI con 1ª migration mergeada y aplicada en staging.
- [ ] CI gate `migrate-check` bloquea PRs con migrations destructivas no expand-contract.
- [ ] Drift detector corriendo weekly, alertas en Slack.
- [ ] DR drill ejecutado y documentado en S5.
- [ ] Rollback runbook probado al menos 1 vez en staging.

---

## 5. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Dev hace cambio en Supabase Studio sin commit | Drift, bugs prod | Drift detector weekly + capacitación + Studio read-only en prod |
| Doppler down → app no arranca | Outage | Cache local de secrets (Doppler CLI lo soporta) + fallback `.env.fallback` cifrado SOPS solo para emergency boot |
| Terraform state corrupted | Pérdida control infra | Versioning en bucket + backup diario state file |
| Migration falla en prod sin rollback | Data loss | Dump pre-deploy obligatorio + downgrade real obligatorio |
| Gitleaks bypass por dev | Leak credenciales | Push protection GitHub native (server-side) + audit logs Doppler |
| Pablo bus factor | Bloqueo total | TI integración MT con role `developer`; runbooks completos en repo |

---

## 6. ADRs propuestos

- **ADR-049 — Migration Discipline (Alembic + Supabase CLI + Expand-Contract)**.
- **ADR-050 — IaC con Terraform y Hetzner provider**.
- **ADR-051 — Secrets Management con Doppler**.

(Ver archivos `adr/ADR-049`, `adr/ADR-050`, `adr/ADR-051`).

---

## 7. TODO / dudas pendientes

1. **Hetzner Object Storage strong consistency** — ¿confirma soporte de locking nativo TF backend o necesitamos DynamoDB-equivalente? Probar en S0; si no, fallback Terraform Cloud free tier.
2. **MT corporate SSO** — ¿MT tiene Microsoft Entra o Google Workspace que permita federarlo con Doppler para que TI integración no use cuentas individuales? Pendiente pregunta a sponsor.
3. **Backups automáticos Hetzner vs. external** — Hetzner snapshots son convenientes pero locked-in al provider. ¿Replicar dump diario a R2 / B2 externo para DR cross-provider? Decisión pendiente costo/beneficio.
