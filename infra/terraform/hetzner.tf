# =============================================================================
# Hetzner Cloud — servers, network, floating IP, firewall, SSH (US-1A-IAC-01)
# =============================================================================
# Provisiona la topología staging/prod MT Pricing:
#   - 1× hcloud_server "app"      — FastAPI + Caddy + frontend Next.js (SSR)
#   - 1× hcloud_server "worker"   — Celery worker + beat
#   - 1× hcloud_server "db_bouncer" — pgbouncer (Postgres mantenido por Supabase
#                                       Cloud — pero bouncer cerca de los apps
#                                       reduce latencia y handles connection
#                                       pooling para Celery).
#   - 1× hcloud_floating_ip       — IP estable para `app.mtme.ae`
#   - 1× hcloud_network           — privada 10.0.0.0/16
#   - 1× hcloud_firewall          — deny all in / allow 22 + 80 + 443 + intra
#   - SSH keys importadas vía var.ssh_public_keys
# =============================================================================
# NOTE Sprint 5: NO ejecutar `terraform apply` aún. Hetzner project + servers
# pendientes de provisión por TI MT. Esta config valida con `terraform validate`
# pero requiere `var.environment=staging` + secrets Doppler para apply.
# =============================================================================

# -----------------------------------------------------------------------------
# Private network (subnet única para todo el plano)
# -----------------------------------------------------------------------------
resource "hcloud_network" "main" {
  name     = "mt-pricing-${var.environment}"
  ip_range = "10.0.0.0/16"
  labels   = local.common_labels
}

resource "hcloud_network_subnet" "main" {
  network_id   = hcloud_network.main.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.0.1.0/24"
}

# -----------------------------------------------------------------------------
# Firewall — deny all ingress, allow only 22/80/443 + intra-network
# -----------------------------------------------------------------------------
resource "hcloud_firewall" "main" {
  name   = "mt-pricing-${var.environment}-fw"
  labels = local.common_labels

  # SSH — restringido a CIDRs admin (whitelist en var.admin_cidrs si presente).
  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "22"
    source_ips = length(var.admin_cidrs) > 0 ? var.admin_cidrs : ["0.0.0.0/0", "::/0"]
  }

  # HTTP — Caddy hace redirect a HTTPS.
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # HTTPS — Caddy auto-cert Let's Encrypt + tráfico Cloudflare.
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # ICMP — útil para ping/healthcheck infra side
  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# -----------------------------------------------------------------------------
# SSH keys — importadas como recursos para permitir rotación declarativa
# -----------------------------------------------------------------------------
resource "hcloud_ssh_key" "admins" {
  for_each   = { for idx, key in var.ssh_public_keys : idx => key }
  name       = "mt-pricing-admin-${each.key}"
  public_key = each.value
  labels     = local.common_labels
}

# -----------------------------------------------------------------------------
# App server — FastAPI + Caddy + frontend SSR
# -----------------------------------------------------------------------------
resource "hcloud_server" "app" {
  name        = "mt-app-${var.environment}"
  server_type = var.server_type
  location    = var.server_location
  image       = "ubuntu-22.04"
  ssh_keys    = [for k in hcloud_ssh_key.admins : k.id]
  firewall_ids = [hcloud_firewall.main.id]
  labels = merge(local.common_labels, {
    role = "app"
  })

  network {
    network_id = hcloud_network.main.id
    ip         = "10.0.1.10"
  }

  user_data = file("${path.module}/cloud-init/app.yaml")

  depends_on = [hcloud_network_subnet.main]
}

# -----------------------------------------------------------------------------
# Worker server — Celery
# -----------------------------------------------------------------------------
resource "hcloud_server" "worker" {
  name        = "mt-worker-${var.environment}"
  server_type = var.worker_server_type
  location    = var.server_location
  image       = "ubuntu-22.04"
  ssh_keys    = [for k in hcloud_ssh_key.admins : k.id]
  firewall_ids = [hcloud_firewall.main.id]
  labels = merge(local.common_labels, {
    role = "worker"
  })

  network {
    network_id = hcloud_network.main.id
    ip         = "10.0.1.20"
  }

  user_data = file("${path.module}/cloud-init/worker.yaml")

  depends_on = [hcloud_network_subnet.main]
}

# -----------------------------------------------------------------------------
# pgbouncer server — connection pooling cerca de apps
# -----------------------------------------------------------------------------
resource "hcloud_server" "db_bouncer" {
  name        = "mt-bouncer-${var.environment}"
  server_type = var.bouncer_server_type
  location    = var.server_location
  image       = "ubuntu-22.04"
  ssh_keys    = [for k in hcloud_ssh_key.admins : k.id]
  firewall_ids = [hcloud_firewall.main.id]
  labels = merge(local.common_labels, {
    role = "db-bouncer"
  })

  network {
    network_id = hcloud_network.main.id
    ip         = "10.0.1.30"
  }

  user_data = file("${path.module}/cloud-init/bouncer.yaml")

  depends_on = [hcloud_network_subnet.main]
}

# -----------------------------------------------------------------------------
# Floating IP — bound al app server, sobrevive reemplazos
# -----------------------------------------------------------------------------
resource "hcloud_floating_ip" "app" {
  type          = "ipv4"
  home_location = var.server_location
  description   = "MT Pricing app — ${var.environment}"
  labels        = local.common_labels
}

resource "hcloud_floating_ip_assignment" "app" {
  floating_ip_id = hcloud_floating_ip.app.id
  server_id      = hcloud_server.app.id
}

# -----------------------------------------------------------------------------
# Outputs locales (ver outputs.tf para los expuestos al consumidor)
# -----------------------------------------------------------------------------
locals {
  app_public_ipv4    = hcloud_floating_ip.app.ip_address
  app_private_ipv4   = "10.0.1.10"
  worker_private_ipv4 = "10.0.1.20"
  bouncer_private_ipv4 = "10.0.1.30"
}
