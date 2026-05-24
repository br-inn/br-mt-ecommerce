# =============================================================================
# Hetzner Storage Box — backups (US-1A-IAC-01)
# =============================================================================
# Storage Box BX11 (1TB, ~3.5 EUR/mes) para backups encriptados de:
#   - Postgres dump (pg_dump nightly via cron del worker server)
#   - Supabase Storage `product-images` mirror semanal
#   - Logs frozen anuales (compliance)
#
# Hetzner Storage Box no tiene API resource en provider hcloud — se gestiona
# manual por TI MT en Hetzner console + se consume vía SFTP. Este archivo
# documenta la config esperada y opcionalmente provisiona credenciales si TI
# expone una API.
# =============================================================================

variable "storage_box_id" {
  description = "ID del Storage Box Hetzner (asignado tras compra manual)."
  type        = string
  default     = ""
}

variable "storage_box_host" {
  description = "Hostname SFTP del Storage Box (e.g. uXXXXX.your-storagebox.de)."
  type        = string
  default     = ""
}

variable "storage_box_user" {
  description = "Usuario SFTP para backups (típicamente uXXXXX)."
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Output — usado por scripts de backup en worker server
# -----------------------------------------------------------------------------
output "storage_box_endpoint" {
  description = "SFTP endpoint para backups."
  value = var.storage_box_host != "" ? format(
    "sftp://%s@%s",
    var.storage_box_user,
    var.storage_box_host,
  ) : ""
}

# -----------------------------------------------------------------------------
# Política de backups (documentación declarativa, no resource).
# Cron en `infra/scripts/backup.sh` (existente Sprint 0):
#   - Daily: pg_dump | age encrypt | sftp put
#   - Weekly: rsync product-images/ to storage-box/images-week-N/
#   - Monthly: tar logs + age + sftp put
#
# Retención:
#   - Daily backups: 30 días
#   - Weekly: 12 semanas
#   - Monthly: 24 meses
# -----------------------------------------------------------------------------
locals {
  backup_retention_policy = {
    daily_keep_days     = 30
    weekly_keep_weeks   = 12
    monthly_keep_months = 24
  }
}
