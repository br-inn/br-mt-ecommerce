# =============================================================================
# Additional input variables for hetzner.tf (US-1A-IAC-01)
# =============================================================================
# Mantenemos `variables.tf` original intacto; las nuevas vars aquí evitan
# colisiones con scaffold S0.
# =============================================================================

variable "admin_cidrs" {
  description = "CIDRs autorizados para SSH (port 22). Vacío = open (sólo dev)."
  type        = list(string)
  default     = []
}

variable "worker_server_type" {
  description = "Hetzner server type para Celery worker."
  type        = string
  default     = "cx22"
}

variable "bouncer_server_type" {
  description = "Hetzner server type para pgbouncer."
  type        = string
  default     = "cx11"
}
