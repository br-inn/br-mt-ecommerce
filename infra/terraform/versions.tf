# =============================================================================
# Terraform + provider version constraints
# =============================================================================
# Pin both Terraform core and providers to avoid surprise breakage.
# Reference: ADR-050 (Terraform on Hetzner Cloud).
# =============================================================================

terraform {
  required_version = ">= 1.7.0, < 2.0.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
    sentry = {
      source  = "jianyuan/sentry"
      version = "~> 0.13"
    }
    better-stack = {
      source  = "BetterStackHQ/betterstack"
      version = "~> 0.4"
    }
    doppler = {
      source  = "DopplerHQ/doppler"
      version = "~> 1.7"
    }
  }

  # Remote state — uncomment once Terraform Cloud / S3-compatible backend is ready.
  # backend "remote" {
  #   organization = "br-innovation"
  #   workspaces { name = "mt-pricing-prod" }
  # }
}
