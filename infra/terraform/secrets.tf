# =============================================================================
# Doppler — referencias a workspace MT (US-1A-IAC-01, ADR-051 + ADR-078)
# =============================================================================
# Doppler funciona como vault de secrets central. Terraform NO crea secrets en
# Doppler aquí (el seedeo lo hace TI MT manual o vía script `doppler-bootstrap.sh`);
# en su lugar referenciamos la config para que módulos downstream consuman.
#
# Patrón:
#   - `doppler-bootstrap.sh` → bootstrap de configs `mt_pricing_staging`/`prd`.
#   - Aplicar `terraform apply` con `doppler run --project mt-pricing --config staging --`
#     que inyecta TF_VAR_hcloud_token, TF_VAR_cloudflare_api_token, etc.
#   - En runtime, los containers Docker leen secrets via `doppler run --` o via
#     `.env` snapshot generado por `infra/scripts/hetzner-deploy.sh`.
# =============================================================================

# Provider Doppler para leer secrets como data sources si fuera necesario.
# (Mayoritariamente usamos var.* injectadas por `doppler run` en CLI.)
variable "doppler_token" {
  description = "Doppler service token (read-only) para data sources. Sourced via env DOPPLER_TOKEN."
  type        = string
  sensitive   = true
  default     = ""
}

provider "doppler" {
  doppler_token = var.doppler_token != "" ? var.doppler_token : null
}

# -----------------------------------------------------------------------------
# Workspace MT — declaración del project + configs esperados
# -----------------------------------------------------------------------------
locals {
  doppler_project = "mt-pricing"
  doppler_configs = ["dev", "staging", "prd"]

  # Lista canónica de secrets que TI MT debe seedear en Doppler.
  # Cualquier key extra debe pasar review en ADR-078.
  expected_secrets = [
    # Database
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    # Auth / JWT
    "JWT_SECRET",
    "JWKS_URL",
    # Redis / Celery
    "REDIS_URL",
    "CELERY_BROKER_URL",
    # Observability (US-1A-OBS-01)
    "SENTRY_DSN",
    "SENTRY_DSN_BACKEND",
    "SENTRY_DSN_WORKER",
    "SENTRY_DSN_FRONTEND",
    "BETTER_STACK_LOGS_TOKEN",
    "BETTER_STACK_LOGS_HOST",
    # Adapters red real (US-1A-09-08)
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "SP_API_REFRESH_TOKEN",
    "SP_API_LWA_CLIENT_ID",
    "SP_API_LWA_CLIENT_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    # Hetzner / Cloudflare (sólo en config terraform-runner)
    "HCLOUD_TOKEN",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ZONE_ID",
  ]
}

# -----------------------------------------------------------------------------
# (Opcional) data sources para validar que un secret crítico existe pre-apply.
# Comentado por defecto: requiere DOPPLER_TOKEN read-only del workspace.
# -----------------------------------------------------------------------------
# data "doppler_secrets" "this" {
#   project = local.doppler_project
#   config  = var.environment == "prod" ? "prd" : var.environment
# }
#
# resource "null_resource" "validate_secrets" {
#   triggers = {
#     missing = join(",", [
#       for s in local.expected_secrets :
#       s if !contains(keys(data.doppler_secrets.this.map), s)
#     ])
#   }
#
#   provisioner "local-exec" {
#     when    = create
#     command = self.triggers.missing == "" ? "true" : "echo 'Missing Doppler secrets: ${self.triggers.missing}' && exit 1"
#   }
# }
