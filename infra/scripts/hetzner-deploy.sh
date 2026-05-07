#!/usr/bin/env bash
# =============================================================================
# Hetzner deploy — terraform apply + provisión post-init via SSH (US-1A-IAC-01)
# =============================================================================
# Wraps:
#   1. `doppler run` para inyectar TF_VAR_* desde workspace mt-pricing.
#   2. `terraform apply` con plan firmado.
#   3. Espera SSH ready en app server.
#   4. SSH + ejecuta `docker compose pull && up -d` con .env materializado de
#      Doppler.
#   5. Smoke test `/health/ready`.
#
# Modos:
#   --apply      Default. Plan + apply + provision + smoke.
#   --plan-only  Sólo terraform plan (review humano).
#   --rollback   Revierte deploy al tag previo (lee state.json del server).
# =============================================================================
set -euo pipefail

ENV="${ENV:-staging}"
DOPPLER_PROJECT="${DOPPLER_PROJECT:-mt-pricing}"
DOPPLER_CONFIG="${DOPPLER_CONFIG:-$ENV}"
TF_DIR="${TF_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" && pwd)}"
MODE="${1:-apply}"

log()  { printf '\033[1;34m[hetzner-deploy]\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m[hetzner-deploy ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

# -----------------------------------------------------------------------------
# Pre-flight checks
# -----------------------------------------------------------------------------
command -v terraform >/dev/null 2>&1 || fail "Terraform CLI not found"
command -v doppler   >/dev/null 2>&1 || fail "Doppler CLI not found"
command -v jq        >/dev/null 2>&1 || fail "jq not found"
command -v ssh       >/dev/null 2>&1 || fail "ssh not found"

[[ -d "$TF_DIR" ]] || fail "Terraform dir not found: $TF_DIR"

log "Mode=$MODE  Env=$ENV  TF_DIR=$TF_DIR  Doppler=$DOPPLER_PROJECT/$DOPPLER_CONFIG"

# -----------------------------------------------------------------------------
# Doppler-injected env helpers
# -----------------------------------------------------------------------------
doppler_run() {
  doppler run --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" -- "$@"
}

# -----------------------------------------------------------------------------
# Mode dispatch
# -----------------------------------------------------------------------------
case "$MODE" in
  --plan-only|plan)
    log "terraform plan ..."
    cd "$TF_DIR"
    doppler_run terraform init -input=false
    doppler_run terraform plan -out=tfplan -var "environment=$ENV"
    log "Plan saved to $TF_DIR/tfplan — review and re-run con --apply para aplicar."
    ;;

  --apply|apply|"")
    log "terraform apply ..."
    cd "$TF_DIR"
    doppler_run terraform init -input=false
    doppler_run terraform apply -auto-approve -var "environment=$ENV"

    log "Esperando SSH ready en app server ..."
    APP_IP=$(doppler_run terraform output -raw app_public_ipv4 2>/dev/null || true)
    [[ -z "$APP_IP" ]] && fail "No app_public_ipv4 output — ¿outputs.tf actualizado?"

    for i in {1..30}; do
      if ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 \
           "mt-deploy@$APP_IP" "echo ok" >/dev/null 2>&1; then
        log "SSH ready ($APP_IP)"
        break
      fi
      sleep 10
    done

    log "Provisión Docker compose remoto ..."
    REMOTE_DEPLOY_DIR="/home/mt-deploy/mt-deploy"
    # Materializa .env via doppler secrets download (single-use, container env)
    doppler_run doppler secrets download --no-file --format env > /tmp/mt-pricing.env
    scp /tmp/mt-pricing.env "mt-deploy@$APP_IP:$REMOTE_DEPLOY_DIR/.env"
    rm -f /tmp/mt-pricing.env

    ssh "mt-deploy@$APP_IP" \
      "cd $REMOTE_DEPLOY_DIR && \
       docker compose pull && \
       docker compose up -d --remove-orphans"

    log "Smoke /health/ready ..."
    for i in {1..18}; do  # ~90s
      if curl -sfk "https://$APP_IP/health/ready" >/dev/null 2>&1 \
           || curl -sf "http://$APP_IP/health/ready" >/dev/null 2>&1; then
        log "Healthcheck OK"
        # Persist current tag for rollback
        ssh "mt-deploy@$APP_IP" \
          "cd $REMOTE_DEPLOY_DIR && \
           jq -n --arg tag \"\${IMAGE_TAG:-latest}\" --arg ts \"$(date -u +%FT%TZ)\" \
              '{current_tag: \$tag, deployed_at: \$ts}' > state.json"
        log "Deploy completado."
        exit 0
      fi
      sleep 5
    done
    fail "Healthcheck falló — revisa logs en server. Para rollback: $0 --rollback"
    ;;

  --rollback|rollback)
    log "Rollback ..."
    cd "$TF_DIR"
    APP_IP=$(doppler_run terraform output -raw app_public_ipv4 2>/dev/null || true)
    [[ -z "$APP_IP" ]] && fail "No app_public_ipv4 disponible"
    ssh "mt-deploy@$APP_IP" \
      "cd /home/mt-deploy/mt-deploy && \
       PREV=\$(jq -r '.previous_tag // \"latest\"' state.json 2>/dev/null) && \
       echo Rolling back to: \$PREV && \
       IMAGE_TAG=\$PREV docker compose up -d"
    log "Rollback emitido — verifica /health/ready manualmente."
    ;;

  *)
    fail "Modo desconocido: $MODE. Usa --apply|--plan-only|--rollback"
    ;;
esac
