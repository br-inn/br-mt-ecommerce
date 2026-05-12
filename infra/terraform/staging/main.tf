# =============================================================================
# Terraform root module — MT Pricing Staging (Hetzner Cloud)
# =============================================================================
# Pre-requisites:
#   export HCLOUD_TOKEN=<your-hetzner-api-token>
#   export AWS_ACCESS_KEY_ID=<backblaze-keyID>
#   export AWS_SECRET_ACCESS_KEY=<backblaze-applicationKey>
#
# Usage:
#   terraform init
#   terraform plan -out=tfplan
#   terraform apply tfplan
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = ">= 1.45.0"
    }
  }

  # Backblaze B2 — S3-compatible remote state
  backend "s3" {
    endpoint                    = "https://s3.us-west-004.backblazeb2.com"
    bucket                      = "mt-pricing-tfstate"
    key                         = "staging/terraform.tfstate"
    region                      = "us-west-004"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}

# -----------------------------------------------------------------------------
# Provider
# -----------------------------------------------------------------------------
provider "hcloud" {
  # Token read from HCLOUD_TOKEN env var (never hardcode)
}

# -----------------------------------------------------------------------------
# SSH Key — injected from env/variable, not hardcoded
# -----------------------------------------------------------------------------
variable "ssh_public_key" {
  description = "SSH public key content to inject into servers"
  type        = string
  sensitive   = true
}

resource "hcloud_ssh_key" "deploy" {
  name       = "mt-pricing-staging-deploy"
  public_key = var.ssh_public_key

  labels = {
    managed-by = "terraform"
    project    = "mt-pricing"
    env        = "staging"
  }
}

# -----------------------------------------------------------------------------
# API Server (CX31 — 2 vCPU, 8 GB RAM)
# Runs: backend + worker + beat + frontend + caddy
# -----------------------------------------------------------------------------
module "api_server" {
  source = "../modules/hetzner-server"

  server_name = "mt-pricing-api-staging"
  server_type = "cx31"
  location    = "nbg1"
  image       = "ubuntu-22.04"
  ssh_key_ids = [hcloud_ssh_key.deploy.id]

  labels = {
    env     = "staging"
    role    = "api"
    project = "mt-pricing"
  }
}

# -----------------------------------------------------------------------------
# Worker Server (CX21 — 2 vCPU, 4 GB RAM)
# Runs: worker + beat (heavy Celery tasks isolated)
# -----------------------------------------------------------------------------
module "worker_server" {
  source = "../modules/hetzner-server"

  server_name = "mt-pricing-worker-staging"
  server_type = "cx21"
  location    = "nbg1"
  image       = "ubuntu-22.04"
  ssh_key_ids = [hcloud_ssh_key.deploy.id]

  labels = {
    env     = "staging"
    role    = "worker"
    project = "mt-pricing"
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "api_server_ip" {
  description = "Public IPv4 of the API/frontend server"
  value       = module.api_server.ipv4_address
}

output "worker_server_ip" {
  description = "Public IPv4 of the worker server"
  value       = module.worker_server.ipv4_address
}

output "api_server_id" {
  value = module.api_server.server_id
}

output "worker_server_id" {
  value = module.worker_server.server_id
}
