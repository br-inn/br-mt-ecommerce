# =============================================================================
# Hetzner Cloud — root module
# =============================================================================
# Sprint 0 placeholder. Concrete server/firewall/network/DNS resources land in
# Sprint 1 per ADR-050. Keeping this minimal so `terraform validate` passes
# and CI gates are exercised end to end from day 1.
# =============================================================================

provider "hcloud" {
  token = var.hcloud_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# -----------------------------------------------------------------------------
# Tags / labels applied to every resource for cost attribution and lifecycle.
# -----------------------------------------------------------------------------
locals {
  common_labels = {
    project     = "mt-pricing"
    environment = var.environment
    managed_by  = "terraform"
    owner       = "br-innovation"
  }
}

# -----------------------------------------------------------------------------
# Private network — placeholder. Real subnets + routes come in Sprint 1.
# -----------------------------------------------------------------------------
# resource "hcloud_network" "main" {
#   name     = "mt-pricing-${var.environment}"
#   ip_range = "10.0.0.0/16"
#   labels   = local.common_labels
# }

# TODO(infra-sprint-1): server module (CX22 or CPX21) for app + worker.
# TODO(infra-sprint-1): firewall (deny all in, allow 22/80/443 + private net).
# TODO(infra-sprint-1): managed Postgres (or self-hosted on dedicated node).
# TODO(infra-sprint-1): Cloudflare DNS records pointing to floating IP.
# TODO(infra-sprint-1): Hetzner Object Storage bucket for backups.
