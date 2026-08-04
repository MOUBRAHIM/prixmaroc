#!/usr/bin/env bash
# setup_vps.sh — Configuration initiale d'un VPS Ubuntu 22.04 LTS
# À exécuter UNE SEULE FOIS sur le VPS fraîchement créé (en root)
# Usage : curl -sSL https://raw.githubusercontent.com/TON_USER/prixmaroc/main/scripts/setup_vps.sh | bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${BLUE}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════╗"
echo "║     PrixMaroc — Setup VPS Ubuntu 22.04       ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Mise à jour système ────────────────────────────────────────────────────
info "Mise à jour du système..."
apt-get update -qq && apt-get upgrade -y -qq
log "Système à jour"

# ── 2. Paquets essentiels ─────────────────────────────────────────────────────
info "Installation des paquets de base..."
apt-get install -y -qq \
  git curl wget unzip ufw fail2ban \
  ca-certificates gnupg lsb-release \
  htop tmux vim
log "Paquets installés"

# ── 3. Docker ─────────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  info "Installation de Docker..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  log "Docker installé ($(docker --version))"
else
  log "Docker déjà installé"
fi

# ── 4. Utilisateur deploy ────────────────────────────────────────────────────
if ! id "deploy" &>/dev/null; then
  info "Création de l'utilisateur deploy..."
  useradd -m -s /bin/bash deploy
  usermod -aG docker deploy
  mkdir -p /home/deploy/.ssh
  # Copier les clés SSH de root vers deploy
  [ -f /root/.ssh/authorized_keys ] && \
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
  chown -R deploy:deploy /home/deploy/.ssh
  chmod 700 /home/deploy/.ssh
  chmod 600 /home/deploy/.ssh/authorized_keys 2>/dev/null || true
  log "Utilisateur 'deploy' créé"
fi

# ── 5. Firewall UFW ───────────────────────────────────────────────────────────
info "Configuration du pare-feu..."
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow ssh >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
log "Firewall actif (SSH + 80 + 443)"

# ── 6. Fail2ban ───────────────────────────────────────────────────────────────
systemctl enable fail2ban
systemctl start fail2ban
log "Fail2ban actif"

# ── 7. Clone du dépôt ────────────────────────────────────────────────────────
REPO_DIR="/opt/prixmaroc"
if [ ! -d "$REPO_DIR" ]; then
  info "Clone du dépôt..."
  git clone https://github.com/TON_USER/prixmaroc.git "$REPO_DIR"
  chown -R deploy:deploy "$REPO_DIR"
  log "Dépôt cloné dans $REPO_DIR"
else
  warn "Dépôt déjà présent dans $REPO_DIR"
fi

# ── 8. Fichier .env.production ────────────────────────────────────────────────
ENV_FILE="$REPO_DIR/backend/.env.production"
if [ ! -f "$ENV_FILE" ]; then
  info "Copie du template .env.production..."
  cp "$REPO_DIR/backend/.env.production.example" "$ENV_FILE"
  warn "⚠  IMPORTANT : éditez $ENV_FILE avant de continuer !"
  warn "   nano $ENV_FILE"
fi

# ── 9. Certificat SSL Let's Encrypt (bootstrap) ───────────────────────────────
cat <<'EOF'

╔══════════════════════════════════════════════════════════════╗
║   ✅ VPS configuré !  Prochaines étapes :                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  1. Pointer le DNS :                                         ║
║     prixmaroc.ma    →  IP_DE_VOTRE_VPS                      ║
║     www.prixmaroc.ma →  IP_DE_VOTRE_VPS                     ║
║                                                              ║
║  2. Éditer les variables d'environnement :                   ║
║     nano /opt/prixmaroc/backend/.env.production              ║
║                                                              ║
║  3. Obtenir le certificat SSL :                              ║
║     cd /opt/prixmaroc                                        ║
║     bash scripts/init_ssl.sh                                 ║
║                                                              ║
║  4. Lancer le déploiement :                                  ║
║     bash scripts/deploy.sh                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
