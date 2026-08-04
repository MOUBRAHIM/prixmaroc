#!/usr/bin/env bash
# ============================================================================
# backup_r2.sh — Sauvegarde automatique PostgreSQL → Cloudflare R2
#
# Usage:
#   ./scripts/backup_r2.sh
#
# Variables d'environnement requises (dans /opt/prixmaroc/.env ou exportées) :
#   DATABASE_URL        — URL PostgreSQL complète (ex: postgresql://user:pass@localhost/db)
#   R2_ACCOUNT_ID       — ID de compte Cloudflare
#   R2_ACCESS_KEY_ID    — Clé d'accès R2
#   R2_SECRET_ACCESS_KEY — Clé secrète R2
#   R2_BUCKET_NAME      — Nom du bucket (ex: prixmaroc-backups)
#
# Cron recommandé (sur le VPS) :
#   0 2 * * * /opt/prixmaroc/scripts/backup_r2.sh >> /var/log/prixmaroc_backup.log 2>&1
# ============================================================================

set -euo pipefail

# ── Chargement .env si disponible ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
fi

# ── Vérification des variables obligatoires ────────────────────────────────────
REQUIRED_VARS=(DATABASE_URL R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME)
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "[backup_r2] ❌ Variable manquante: $var" >&2
    exit 1
  fi
done

# ── Configuration ──────────────────────────────────────────────────────────────
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="/tmp/prixmaroc_backup_${TIMESTAMP}.sql.gz"
R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_KEY="backups/postgres/${TIMESTAMP}/prixmaroc_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30   # Conserver les backups X jours

# ── Extraction des paramètres PostgreSQL depuis DATABASE_URL ──────────────────
# Format: postgresql+asyncpg://user:pass@host:port/dbname
# ou:     postgresql://user:pass@host:port/dbname
DB_URL="${DATABASE_URL}"
DB_URL="${DB_URL#postgresql+asyncpg://}"
DB_URL="${DB_URL#postgresql://}"

DB_USER="${DB_URL%%:*}"
DB_URL="${DB_URL#*:}"
DB_PASS="${DB_URL%%@*}"
DB_URL="${DB_URL#*@}"
DB_HOST="${DB_URL%%/*}"
DB_NAME="${DB_URL##*/}"
DB_PORT="5432"

# Gestion port custom dans l'host (host:port)
if [[ "$DB_HOST" == *:* ]]; then
  DB_PORT="${DB_HOST##*:}"
  DB_HOST="${DB_HOST%%:*}"
fi

echo "[backup_r2] $(date '+%Y-%m-%d %H:%M:%S') — Démarrage backup"
echo "[backup_r2] Base: ${DB_NAME}@${DB_HOST}:${DB_PORT}"

# ── pg_dump ───────────────────────────────────────────────────────────────────
echo "[backup_r2] pg_dump en cours…"
PGPASSWORD="$DB_PASS" pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --no-owner \
  --no-acl \
  --format=plain \
  --compress=9 \
  | gzip -9 > "$BACKUP_FILE"

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "[backup_r2] Dump terminé — taille: ${BACKUP_SIZE}"

# ── Upload vers Cloudflare R2 (via AWS CLI) ───────────────────────────────────
echo "[backup_r2] Upload vers R2 (${R2_BUCKET_NAME}/${R2_KEY})…"

AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
aws s3 cp "$BACKUP_FILE" \
  "s3://${R2_BUCKET_NAME}/${R2_KEY}" \
  --endpoint-url "$R2_ENDPOINT" \
  --region auto \
  --storage-class STANDARD \
  --metadata "db=${DB_NAME},timestamp=${TIMESTAMP},host=${DB_HOST}"

echo "[backup_r2] ✅ Upload réussi: s3://${R2_BUCKET_NAME}/${R2_KEY}"

# ── Nettoyage local ───────────────────────────────────────────────────────────
rm -f "$BACKUP_FILE"
echo "[backup_r2] Fichier temporaire supprimé"

# ── Rotation des vieux backups (> RETENTION_DAYS jours) ──────────────────────
echo "[backup_r2] Rotation des backups > ${RETENTION_DAYS} jours…"

CUTOFF_DATE=$(date -d "${RETENTION_DAYS} days ago" +"%Y%m%d" 2>/dev/null \
  || date -v-${RETENTION_DAYS}d +"%Y%m%d" 2>/dev/null \
  || echo "00000000")

if [[ "$CUTOFF_DATE" != "00000000" ]]; then
  # Liste les objets dans le préfixe backups/postgres/
  OLD_KEYS=$(AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
    aws s3 ls "s3://${R2_BUCKET_NAME}/backups/postgres/" \
      --endpoint-url "$R2_ENDPOINT" \
      --region auto \
      --recursive \
    | awk '{print $4}' \
    | grep -E "prixmaroc_[0-9]{8}" \
    | while read -r key; do
        FILE_DATE=$(echo "$key" | grep -oE "[0-9]{8}" | head -1)
        if [[ "$FILE_DATE" < "$CUTOFF_DATE" ]]; then
          echo "$key"
        fi
      done || true)

  if [[ -n "$OLD_KEYS" ]]; then
    echo "$OLD_KEYS" | while read -r old_key; do
      echo "[backup_r2] Suppression ancien backup: $old_key"
      AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
        AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
        aws s3 rm "s3://${R2_BUCKET_NAME}/${old_key}" \
          --endpoint-url "$R2_ENDPOINT" \
          --region auto
    done
    echo "[backup_r2] Rotation terminée"
  else
    echo "[backup_r2] Aucun backup à supprimer"
  fi
fi

echo "[backup_r2] $(date '+%Y-%m-%d %H:%M:%S') — Backup complet ✅"
