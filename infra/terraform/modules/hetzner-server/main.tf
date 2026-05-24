# =============================================================================
# Module: hetzner-server
# Creates a Hetzner Cloud server with firewall (22/80/443 only).
# =============================================================================

# -----------------------------------------------------------------------------
# Firewall — deny-all ingress, allow SSH + HTTP + HTTPS only
# -----------------------------------------------------------------------------
resource "hcloud_firewall" "this" {
  name = "${var.server_name}-fw"

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "SSH"
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTP (Caddy redirect)"
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTPS"
  }

  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTPS/3 (QUIC)"
  }

  labels = var.labels
}

# -----------------------------------------------------------------------------
# Server
# -----------------------------------------------------------------------------
resource "hcloud_server" "this" {
  name        = var.server_name
  server_type = var.server_type
  image       = var.image
  location    = var.location
  ssh_keys    = var.ssh_key_ids
  user_data   = var.user_data != "" ? var.user_data : null

  firewall_ids = [hcloud_firewall.this.id]

  labels = merge(var.labels, {
    managed-by = "terraform"
    project    = "mt-pricing"
  })

  lifecycle {
    # Prevent accidental server replacement when only labels change.
    ignore_changes = [user_data]
  }
}
