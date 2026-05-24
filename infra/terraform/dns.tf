# =============================================================================
# Cloudflare DNS — registros para `mt-pricing.mt-me.ae` (US-1A-IAC-01)
# =============================================================================
# DNS-only por defecto (sin proxy CF) en staging para que Caddy maneje TLS via
# Let's Encrypt sin DNS-01 challenge. En producción se proxy a través de CF
# para WAF/rate limiting (US-1A-SEC-01).
# =============================================================================

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID para mt-me.ae. Sourced from Doppler."
  type        = string
  sensitive   = true
}

variable "dns_subdomain" {
  description = "Subdominio público (e.g. mt-pricing, mt-pricing-staging)."
  type        = string
  default     = "mt-pricing"
}

variable "cloudflare_proxy_enabled" {
  description = "Si true, registros A pasan por proxy Cloudflare (WAF activo)."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# A record — apex subdominio → floating IP del app server
# -----------------------------------------------------------------------------
resource "cloudflare_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = var.dns_subdomain
  type    = "A"
  value   = hcloud_floating_ip.app.ip_address
  ttl     = var.cloudflare_proxy_enabled ? 1 : 300 # TTL=1 cuando proxy on
  proxied = var.cloudflare_proxy_enabled
  comment = "MT Pricing — managed by Terraform"
}

# -----------------------------------------------------------------------------
# CNAME api.* → apex (separación opcional para futuras rutas)
# -----------------------------------------------------------------------------
resource "cloudflare_record" "api_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "api.${var.dns_subdomain}"
  type    = "CNAME"
  value   = "${var.dns_subdomain}.${var.domain}"
  ttl     = 1
  proxied = var.cloudflare_proxy_enabled
}

# -----------------------------------------------------------------------------
# TXT — verificación SPF (mailer transaccional outbound)
# -----------------------------------------------------------------------------
resource "cloudflare_record" "spf" {
  zone_id = var.cloudflare_zone_id
  name    = var.dns_subdomain
  type    = "TXT"
  value   = "v=spf1 include:_spf.mailgun.org -all"
  ttl     = 3600
}

# -----------------------------------------------------------------------------
# CAA — sólo Let's Encrypt + Cloudflare pueden emitir certs
# -----------------------------------------------------------------------------
resource "cloudflare_record" "caa_letsencrypt" {
  zone_id = var.cloudflare_zone_id
  name    = var.dns_subdomain
  type    = "CAA"
  data {
    flags = 0
    tag   = "issue"
    value = "letsencrypt.org"
  }
  ttl = 3600
}

resource "cloudflare_record" "caa_cf" {
  zone_id = var.cloudflare_zone_id
  name    = var.dns_subdomain
  type    = "CAA"
  data {
    flags = 0
    tag   = "issue"
    value = "pki.goog"
  }
  ttl = 3600
}
