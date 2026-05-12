#!/usr/bin/env bash
# =============================================================================
# bootstrap-server.sh — Configuración inicial del servidor Hetzner (Ubuntu 22.04)
# =============================================================================
# Ejecutar UNA VEZ por SSH como root tras provisionar el servidor con Terraform:
#   ssh root@<SERVER_IP> 'bash -s' < scripts/bootstrap-server.sh
#
# Idempotente: re-ejecutar es seguro.
# =============================================================================
set -euo pipefail

SERVER_IP="${1:-}"
log() { echo "[bootstrap] $(date -u +%H:%M:%S) $*"; }

# ---------------------------------------------------------------------------
# 1. Actualizar sistema
# ---------------------------------------------------------------------------
log "Actualizando paquetes base..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

# ---------------------------------------------------------------------------
# 2. Docker v24+ y Docker Compose v2
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
  log "Instalando Docker..."
  apt-get install -y -qq ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  log "Docker instalado: $(docker --version)"
else
  log "Docker ya instalado: $(docker --version)"
fi

# ---------------------------------------------------------------------------
# 3. UFW — deny all, allow 22/80/443
# ---------------------------------------------------------------------------
log "Configurando UFW..."
apt-get install -y -qq ufw
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP (Caddy redirect)"
ufw allow 443/tcp  comment "HTTPS"
ufw allow 443/udp  comment "HTTPS/3 QUIC"
ufw --force enable
log "UFW status:"
ufw status verbose

# ---------------------------------------------------------------------------
# 4. SSH hardening
# ---------------------------------------------------------------------------
log "Aplicando SSH hardening..."
SSHD_CONF="/etc/ssh/sshd_config"
# Crear backup idempotente
cp -n "${SSHD_CONF}" "${SSHD_CONF}.orig" || true

# Deshabilitar autenticación por contraseña
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CONF}"
grep -q "^PasswordAuthentication no" "${SSHD_CONF}" \
  || echo "PasswordAuthentication no" >> "${SSHD_CONF}"

# Prohibir login root directo por contraseña (permite clave SSH)
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "${SSHD_CONF}"
grep -q "^PermitRootLogin prohibit-password" "${SSHD_CONF}" \
  || echo "PermitRootLogin prohibit-password" >> "${SSHD_CONF}"

systemctl reload sshd
log "SSH hardening aplicado."

# ---------------------------------------------------------------------------
# 5. Doppler CLI
# ---------------------------------------------------------------------------
if ! command -v doppler &>/dev/null; then
  log "Instalando Doppler CLI..."
  curl -Ls --tlsv1.2 --proto "=https" https://cli.doppler.com/install.sh | sh
  log "Doppler instalado: $(doppler --version)"
else
  log "Doppler ya instalado: $(doppler --version)"
fi

# ---------------------------------------------------------------------------
# 6. Usuario deploy
# ---------------------------------------------------------------------------
if ! id deploy &>/dev/null; then
  log "Creando usuario deploy..."
  useradd -m -s /bin/bash deploy
  usermod -aG docker deploy
  # sudo sin password solo para docker (principio de mínimo privilegio)
  echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker compose" \
    > /etc/sudoers.d/deploy-docker
  chmod 0440 /etc/sudoers.d/deploy-docker

  # Copiar authorized_keys de root al usuario deploy
  if [ -f /root/.ssh/authorized_keys ]; then
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    chmod 600 /home/deploy/.ssh/authorized_keys
  fi
  log "Usuario deploy creado."
else
  log "Usuario deploy ya existe."
  usermod -aG docker deploy 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# 7. Directorio de trabajo del proyecto
# ---------------------------------------------------------------------------
log "Creando /opt/mt-pricing/..."
mkdir -p /opt/mt-pricing
chown -R deploy:deploy /opt/mt-pricing
chmod 750 /opt/mt-pricing
log "Directorio /opt/mt-pricing listo."

# ---------------------------------------------------------------------------
# Verificación final
# ---------------------------------------------------------------------------
log "=== Bootstrap completado ==="
log "Docker:  $(docker --version)"
log "Compose: $(docker compose version)"
log "Doppler: $(doppler --version)"
log "UFW:     $(ufw status | head -1)"
log ""
log "Próximo paso: configurar Doppler y ejecutar deploy-staging.sh"
