#!/usr/bin/env bash
# init_ssl.sh — Obtention du certificat Let's Encrypt (première fois)
# À exécuter APRÈS avoir pointé le DNS vers le VPS
# Usage : bash scripts/init_ssl.sh
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${BLUE}[→]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEPLOY_DIR"

# Charger les variables pour récupérer DOMAIN et EMAIL
[ -f "backend/.env.production" ] && source backend/.env.production
DOMAIN="${DOMAIN:-prixmaroc.ma}"
EMAIL="${LETSENCRYPT_EMAIL:-admin@prixmaroc.ma}"

info "Domaine : $DOMAIN"
info "Email   : $EMAIL"

# ── Étape 1 : Nginx HTTP uniquement (pour le challenge ACME) ──────────────────
info "Démarrage nginx HTTP (challenge Let's Encrypt)..."
cat > /tmp/nginx_bootstrap.conf <<NGINX
events { worker_connections 1024; }
http {
    server {
        listen 80;
        server_name ${DOMAIN} www.${DOMAIN};
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        location / {
            return 200 'Bootstrap OK';
            add_header Content-Type text/plain;
        }
    }
}
NGINX

docker run -d --name nginx_bootstrap \
  -p 80:80 \
  -v /tmp/nginx_bootstrap.conf:/etc/nginx/nginx.conf:ro \
  -v certbot_www:/var/www/certbot \
  nginx:alpine 2>/dev/null || true

sleep 3

# ── Étape 2 : Obtenir le certificat ──────────────────────────────────────────
info "Obtention du certificat SSL pour $DOMAIN..."
docker run --rm \
  -v certbot_conf:/etc/letsencrypt \
  -v certbot_www:/var/www/certbot \
  certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

# ── Étape 3 : Arrêter le nginx bootstrap ──────────────────────────────────────
docker stop nginx_bootstrap && docker rm nginx_bootstrap 2>/dev/null || true
log "Certificat SSL obtenu pour $DOMAIN"

# ── Étape 4 : Créer les volumes Docker nommés pour la prod ───────────────────
docker volume create certbot_conf >/dev/null 2>&1 || true
docker volume create certbot_www  >/dev/null 2>&1 || true
log "Volumes certbot créés"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ SSL configuré !  Lancez maintenant :  ║${NC}"
echo -e "${GREEN}║     bash scripts/deploy.sh                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
