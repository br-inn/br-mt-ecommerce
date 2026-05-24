# =============================================================================
# Outputs
# =============================================================================
# Values exposed for downstream tooling (deploy scripts, monitoring, etc.).
# Sprint 0 placeholders. Real outputs depend on resources implemented in
# Sprint 1 (servers, IPs, hostnames).
# =============================================================================

output "environment" {
  description = "Deployment environment label."
  value       = var.environment
}

output "domain" {
  description = "Configured public domain."
  value       = var.domain
}

# TODO(infra-sprint-1): expose floating_ip, server_ipv4, server_ipv6,
# database_dsn (sensitive), object_storage_endpoint, etc.

output "sentry_backend_dsn" {
  description = "Sentry DSN backend project."
  value       = var.sentry_auth_token != "" ? sentry_project.backend[0].dsn_public : ""
  sensitive   = true
}

output "sentry_worker_dsn" {
  description = "Sentry DSN worker project."
  value       = var.sentry_auth_token != "" ? sentry_project.worker[0].dsn_public : ""
  sensitive   = true
}

output "sentry_frontend_dsn" {
  description = "Sentry DSN frontend project."
  value       = var.sentry_auth_token != "" ? sentry_project.frontend[0].dsn_public : ""
  sensitive   = true
}
