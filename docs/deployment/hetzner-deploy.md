# Guía de Deploy: MT Pricing en Hetzner Cloud (Staging)

## Resumen

Stack: Docker Compose + Caddy 2 (auto-TLS) + FastAPI + Next.js + Celery + Redis  
Infra: Terraform (Backblaze B2 remote state) + Hetzner Cloud (nbg1)  
Secrets: Doppler CLI (no `.env` en disco en producción)

---

## Pre-requisitos

| Requisito | Dónde obtener |
|---|---|
| Hetzner Cloud API Token | Hetzner Console → Proyecto → Security → API Tokens |
| SSH key pair | `ssh-keygen -t ed25519 -C "deploy-staging"` |
| Doppler token (project `mt-pricing`, config `staging`) | Doppler Dashboard → Service Tokens |
| Backblaze B2 bucket `mt-pricing-tfstate` | Backblaze Console → B2 Buckets |
| Backblaze App Key con acceso al bucket | Backblaze Console → App Keys |
| Docker + Terraform 1.5+ instalados localmente | https://developer.hashicorp.com/terraform/install |

---

## AC 1 — Terraform provisiona servidor Hetzner sin error

### 1.1 Exportar credenciales

```bash
export HCLOUD_TOKEN="<hetzner-api-token>"
export AWS_ACCESS_KEY_ID="<backblaze-key-id>"
export AWS_SECRET_ACCESS_KEY="<backblaze-app-key>"
export TF_VAR_ssh_public_key="$(cat ~/.ssh/id_ed25519_deploy.pub)"
```

### 1.2 Inicializar y aplicar Terraform

```bash
cd infra/terraform/staging

terraform init

terraform plan -out=tfplan

terraform apply tfplan
```

Terraform imprime las IPs al terminar:

```
api_server_ip    = "X.X.X.X"
worker_server_ip = "Y.Y.Y.Y"
```

Guardar esas IPs para los pasos siguientes.

---

## AC 2 — Bootstrap del servidor (una sola vez)

Ejecutar `bootstrap-server.sh` en cada servidor como `root`:

```bash
# Servidor API
ssh root@<API_IP> 'bash -s' < scripts/bootstrap-server.sh

# Servidor Worker (si diferente)
ssh root@<WORKER_IP> 'bash -s' < scripts/bootstrap-server.sh
```

El script instala: Docker v24+, Docker Compose v2, UFW (22/80/443), Doppler CLI, usuario `deploy`, directorio `/opt/mt-pricing/`.

---

## AC 3 — Configurar Doppler en el servidor

Conectar por SSH como `deploy` y configurar Doppler:

```bash
ssh deploy@<API_IP>

# Autenticar con token de servicio (no interactivo)
doppler configure set token <DOPPLER_SERVICE_TOKEN>
doppler configure set project mt-pricing
doppler configure set config staging

# Verificar
doppler secrets --only-names
```

Repetir en servidor worker si es diferente.

---

## AC 4 — Primer deploy

Desde la máquina local (con acceso SSH al servidor):

```bash
export STAGING_API_HOST="<API_IP>"
export STAGING_WORKER_HOST="<WORKER_IP>"   # puede ser igual a API_IP
export DEPLOY_USER="deploy"
export STAGING_DOMAIN="staging.mt-pricing.com"

chmod +x scripts/deploy-staging.sh
./scripts/deploy-staging.sh latest
```

El script:
1. Copia `docker-compose.staging.yml` y `Caddyfile.staging` al servidor
2. Hace `docker compose pull` con la imagen indicada
3. Levanta el stack con `docker compose up -d --remove-orphans`
4. Ejecuta `alembic upgrade head`
5. Verifica `https://staging.mt-pricing.com/health/ready` → HTTP 200

---

## AC 5 — DNS

Crear registro A en tu proveedor DNS:

```
staging.mt-pricing.com  A  <API_IP>  TTL 300
```

Caddy obtiene el certificado TLS automáticamente al recibir la primera petición HTTPS.

---

## AC 6 — Verificación completa

```bash
# Health live (backend)
curl -s https://staging.mt-pricing.com/health/live

# Health ready (backend + DB + Redis)
curl -s https://staging.mt-pricing.com/health/ready

# Frontend
curl -s -o /dev/null -w "%{http_code}" https://staging.mt-pricing.com/

# OpenAPI
curl -s https://staging.mt-pricing.com/openapi.json | python3 -m json.tool | head -5
```

Todos deben responder HTTP 200.

---

## Rollback

Para volver a una imagen anterior (target < 2 min):

```bash
export STAGING_API_HOST="<API_IP>"
export STAGING_WORKER_HOST="<WORKER_IP>"
export DEPLOY_USER="deploy"

chmod +x scripts/rollback-staging.sh
./scripts/rollback-staging.sh 1.2.2   # tag anterior
```

Si el rollback cruza una migración de schema, ejecutar manualmente:

```bash
ssh deploy@<API_IP>
cd /opt/mt-pricing
doppler run -- docker compose -f docker-compose.staging.yml exec backend \
  alembic downgrade -1
```

---

## Estructura de archivos

```
infra/
  terraform/
    modules/
      hetzner-server/
        main.tf          # hcloud_server + hcloud_firewall
        variables.tf     # server_type, location, ssh_key_ids, ...
        outputs.tf       # ipv4_address, server_id
        versions.tf      # hcloud >= 1.45.0, terraform >= 1.5.0
    staging/
      main.tf            # root module (api_server + worker_server + backend S3)
scripts/
  bootstrap-server.sh    # configuración inicial (Docker, UFW, Doppler, deploy user)
  deploy-staging.sh      # deploy por tag
  rollback-staging.sh    # rollback rápido
docker-compose.staging.yml
Caddyfile.staging
.env.staging.example
```

---

## Notas de seguridad

- **Nunca** commitear `.env.staging` con valores reales (está en `.gitignore`).
- Usar **Doppler Service Tokens** (scope: staging read-only) en CI/CD, no tokens personales.
- El firewall Hetzner + UFW bloquean todos los puertos excepto 22/80/443.
- `PasswordAuthentication no` en SSH — solo acceso por clave.
- Hetzner API token exportado como variable de entorno, nunca en ficheros tracked por git.
