#!/usr/bin/env bash
# deploy.sh — Déploiement production PrixMaroc (zéro downtime)
# Usage : ./scripts/deploy.sh [--skip-pull] [--skip-migrate] [--skip-seed]
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${BLUE}[i]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Options ───────────────────────────────────────────────────────────────────
SKIP_PULL=false; SKIP_MIGRATE=false; SKIP_SEED=false
for arg in "$@"; do
  case $arg in
    --skip-pull)    SKIP_PULL=true ;;
    --skip-migrate) SKIP_MIGRATE=true ;;
    --skip-seed)    SKIP_SEED=true ;;
  esac
done

# ── Vérifications ─────────────────────────────────────────────────────────────
DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEPLOY_DIR"
info "Répertoire de déploiement : $DEPLOY_DIR"

[ -f "backend/.env.production" ] || err "backend/.env.production introuvable. Copiez .env.production.example et remplissez les valeurs."
[ -f "docker-compose.prod.yml" ] || err "docker-compose.prod.yml introuvable."
command -v docker >/dev/null 2>&1 || err "Docker non installé."

# Charger les variables prod pour les scripts suivants
set -a; source backend/.env.production; set +a

# ── 1. Mise à jour du code ────────────────────────────────────────────────────
if [ "$SKIP_PULL" = false ]; then
  info "Pull du code depuis GitHub..."
  git pull origin main
  log "Code mis à jour"
fi

# ── 2. Build de l'image backend ───────────────────────────────────────────────
info "Build de l'image backend (prod)..."
docker compose -f docker-compose.prod.yml build --no-cache backend
log "Image backend construite"

# ── 3. Démarrage DB + Redis ───────────────────────────────────────────────────
info "Démarrage PostgreSQL + Redis..."
docker compose -f docker-compose.prod.yml up -d db redis
info "Attente de la santé DB (max 60s)..."
for i in $(seq 1 12); do
  if docker compose -f docker-compose.prod.yml exec -T db pg_isready -U "${POSTGRES_USER:-prixmaroc}" >/dev/null 2>&1; then
    log "PostgreSQL prêt"
    break
  fi
  [ $i -eq 12 ] && err "PostgreSQL n'a pas démarré dans les 60s"
  sleep 5
done

# ── 4. Migrations Alembic ────────────────────────────────────────────────────
if [ "$SKIP_MIGRATE" = false ]; then
  info "Exécution des migrations Alembic..."
  docker compose -f docker-compose.prod.yml run --rm backend sh -c "alembic upgrade head"
  log "Migrations terminées"
fi

# ── 5. Déploiement zéro downtime ─────────────────────────────────────────────
info "Déploiement backend (zéro downtime)..."
# Scale à 2 instances → attendre santé → revenir à 1
docker compose -f docker-compose.prod.yml up -d --scale backend=2 --no-recreate backend
sleep 10
docker compose -f docker-compose.prod.yml up -d --scale backend=1 --no-recreate backend
log "Backend déployé"

# ── 6. Nginx ─────────────────────────────────────────────────────────────────
info "Démarrage/reload Nginx..."
docker compose -f docker-compose.prod.yml up -d nginx
docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload 2>/dev/null || true
log "Nginx actif"

# ── 7. Seed initial (seulement si première installation) ─────────────────────
if [ "$SKIP_SEED" = false ]; then
  PROD_COUNT=$(docker compose -f docker-compose.prod.yml exec -T db \
    psql -U "${POSTGRES_USER:-prixmaroc}" -d "${POSTGRES_DB:-prixmaroc}" -tAc \
    "SELECT COUNT(*) FROM stores;" 2>/dev/null || echo "0")
  PROD_COUNT=$(echo "$PROD_COUNT" | tr -d '[:space:]')
  if [ "${PROD_COUNT:-0}" -lt "100" ]; then
    info "Base vide — seed initial (magasins + produits synthétiques)..."
    docker compose -f docker-compose.prod.yml exec -T backend \
      python /app/seed_database.py --stores-only 2>&1 | grep -E "✓|✗|insérés" || true
    docker compose -f docker-compose.prod.yml exec -T backend \
      python /app/seed_database.py --products-only --synthetic 2>&1 | grep -E "✓|✗|insérés" || true
    log "Seed terminé"
  else
    info "Base déjà peuplée ($PROD_COUNT magasins) — seed ignoré"
  fi
fi

# ── 8. Health check final ─────────────────────────────────────────────────────
info "Vérification santé de l'API..."
DOMAIN="${DOMAIN:-prixmaroc.ma}"
for i in $(seq 1 10); do
  if curl -sf "https://${DOMAIN}/health" >/dev/null 2>&1; then
    log "API accessible sur https://${DOMAIN}/health"
    break
  elif curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
    log "API accessible en local sur http://localhost:8000/health"
    break
  fi
  [ $i -eq 10 ] && warn "Health check échoué après 10 tentatives — vérifiez les logs"
  sleep 6
done

# ── 9. Nettoyage images orphelines ───────────────────────────────────────────
docker image prune -f >/dev/null 2>&1 || true

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       ✅  Déploiement terminé !          ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  API   : https://${DOMAIN}/docs          ${NC}"
echo -e "${GREEN}║  Admin : https://${DOMAIN}/admin         ${NC}"
echo -e "${GREEN}║  Santé : https://${DOMAIN}/health        ${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
