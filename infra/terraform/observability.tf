# =============================================================================
# Sentry + Better Stack — providers + recursos (US-1A-OBS-01)
# =============================================================================
# Provider Sentry: jianyuan/sentry — gestiona team/project/keys/alert rules.
# Provider Better Stack: BetterStackHQ/logtail — gestiona log sources.
# Tokens API se inyectan vía Doppler (`SENTRY_AUTH_TOKEN`, `BETTER_STACK_API_TOKEN`).
# NOTE: Better Stack (logtail) resources are commented out pending provider verification.
# =============================================================================

variable "sentry_auth_token" {
  description = "Sentry auth token con scope `project:write,team:read` (Doppler)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_organization_slug" {
  description = "Slug de la organización Sentry MT."
  type        = string
  default     = "mt-middle-east"
}

variable "better_stack_api_token" {
  description = "Better Stack API token (Doppler)."
  type        = string
  sensitive   = true
  default     = ""
}

provider "sentry" {
  token = var.sentry_auth_token != "" ? var.sentry_auth_token : null
}

# Better Stack (logtail) provider — uncomment once source name is verified:
# provider "logtail" {
#   api_token = var.better_stack_api_token != "" ? var.better_stack_api_token : null
# }

# -----------------------------------------------------------------------------
# Sentry team — `mt-pricing`
# -----------------------------------------------------------------------------
resource "sentry_team" "mt_pricing" {
  count        = var.sentry_auth_token != "" ? 1 : 0
  organization = var.sentry_organization_slug
  name         = "MT Pricing Platform"
  slug         = "mt-pricing"
}

# -----------------------------------------------------------------------------
# Sentry projects — backend / worker / frontend
# Sample rates leídos de `infra/observability/sentry-projects.yaml` (declarativo);
# aquí codificamos los 3 proyectos con sample por ambiente.
# -----------------------------------------------------------------------------
locals {
  sentry_traces_sample_rate = {
    development = 1.0
    staging     = 0.10
    production  = 0.05
  }
}

resource "sentry_project" "backend" {
  count        = var.sentry_auth_token != "" ? 1 : 0
  organization = var.sentry_organization_slug
  teams        = [sentry_team.mt_pricing[0].slug]
  name         = "MT Pricing Backend"
  slug         = "mt-pricing-backend"
  platform     = "python-fastapi"
}

resource "sentry_project" "worker" {
  count        = var.sentry_auth_token != "" ? 1 : 0
  organization = var.sentry_organization_slug
  teams        = [sentry_team.mt_pricing[0].slug]
  name         = "MT Pricing Worker"
  slug         = "mt-pricing-worker"
  platform     = "python-celery"
}

resource "sentry_project" "frontend" {
  count        = var.sentry_auth_token != "" ? 1 : 0
  organization = var.sentry_organization_slug
  teams        = [sentry_team.mt_pricing[0].slug]
  name         = "MT Pricing Frontend"
  slug         = "mt-pricing-frontend"
  platform     = "javascript-nextjs"
}

# -----------------------------------------------------------------------------
# Better Stack log sources — uno por servicio + ambiente
# NOTE: Commented out pending confirmation of correct provider source name.
# Replace "logtail_source" with the correct resource type once verified.
# Requires adding to required_providers in versions.tf:
#   logtail = { source = "BetterStackHQ/logtail", version = ">= 0.1" }
# -----------------------------------------------------------------------------
# resource "logtail_source" "backend_staging" {
#   count          = var.better_stack_api_token != "" ? 1 : 0
#   name           = "mt-backend-staging"
#   platform       = "docker"
#   retention_days = 14
# }
#
# resource "logtail_source" "backend_production" {
#   count          = var.better_stack_api_token != "" ? 1 : 0
#   name           = "mt-backend-production"
#   platform       = "docker"
#   retention_days = 30
# }
#
# resource "logtail_source" "worker_staging" {
#   count          = var.better_stack_api_token != "" ? 1 : 0
#   name           = "mt-worker-staging"
#   platform       = "docker"
#   retention_days = 14
# }
#
# resource "logtail_source" "worker_production" {
#   count          = var.better_stack_api_token != "" ? 1 : 0
#   name           = "mt-worker-production"
#   platform       = "docker"
#   retention_days = 30
# }

