# =============================================================================
# Input variables
# =============================================================================
# Secrets are sourced from Doppler at apply time:
#   doppler run --project mt-pricing --config prd -- terraform apply
# Reference: ADR-051 (Doppler).
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev | staging | prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "hcloud_token" {
  description = "Hetzner Cloud API token (sourced from Doppler)."
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit scope (sourced from Doppler)."
  type        = string
  sensitive   = true
}

variable "domain" {
  description = "Public domain name (e.g. mt-pricing.example.com)."
  type        = string
  default     = "mt-pricing.local"
}

variable "ssh_public_keys" {
  description = "List of SSH public keys authorised on servers."
  type        = list(string)
  default     = []
}

variable "server_type" {
  description = "Hetzner server type for the app node."
  type        = string
  default     = "cx22"
}

variable "server_location" {
  description = "Hetzner datacenter location (e.g. nbg1, fsn1, hel1)."
  type        = string
  default     = "nbg1"
}
