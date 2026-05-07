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
