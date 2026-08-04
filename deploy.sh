#!/bin/bash
# deploy.sh — Déploiement PrixMaroc (zero-downtime)
# Usage : ./deploy.sh [--skip-pull] [--skip-migrate]

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SKIP_PULL=false; SKIP_MIGRATE=false
for arg in "$@"; do
  [[ "$arg" == "--skip-pull" ]]    && SKIP_PULL=true
  [[ "$arg" == "--skip-migrate" ]] && SKIP_MIGRATE=true
done

[[ -f "backend/.env.production" ]]  || error "backend/.env.production introuvable !"
[[ -f "docker-compose.prod.yml" ]]  || error "docker-compose.prod.yml introuvable !"
command -v docker >/dev/null 2>&1   || error "Docker non installé !"

$SKIP_PULL || { log "Pull..."; git pull origin main || warn "git pull échoué"; }

log "Build image..."
docker compose -f docker-compose.prod.yml build --no-cache backend

log "Démarrage DB + Redis..."
docker compose -f docker-compose.prod.yml up -d db redis
timeout 30 bash -c 'until docker compose -f docker-compose.prod.yml exec -T db pg_isready -U prixmaroc; do sleep 1; done' \
  || error "PostgreSQL ne répond pas !"

$SKIP_MIGRATE || {
  log "Migrations Alembic..."
  docker compose -f docker-compose.prod.yml run --rm backend sh -c "alembic upgrade head" \
    || error "Migrations échouées !"
}

log "Redémarrage backend..."
docker compose -f docker-compose.prod.yml up -d --no-deps backend
docker compose -f docker-compose.prod.yml up -d nginx

log "Health check..."
sleep 5
for i in $(seq 1 10); do
  curl -sf "http://localhost:8000/health" > /dev/null 2>&1 && { log "✅ Backend OK !"; break; }
  [[ $i -eq 10 ]] && error "Backend ne répond pas !"
  warn "Tentative $i/10..."; sleep 3
done

docker image prune -f
log "🎉 Déploiement terminé ! https://prixmaroc.ma"
