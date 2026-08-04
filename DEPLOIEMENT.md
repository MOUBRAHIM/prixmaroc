# Guide de Déploiement — PrixMaroc

## Prérequis

- VPS Ubuntu 22.04 LTS (recommandé : 4 CPU, 8 Go RAM)
- Docker + Docker Compose installés
- Nom de domaine pointant vers l'IP du VPS
- Compte Firebase (pour les notifications push)
- Compte Sentry (pour le monitoring des erreurs)

---

## 1. Installation initiale sur le VPS

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Installation Docker Compose v2
sudo apt install docker-compose-plugin -y

# Cloner le dépôt
git clone https://github.com/votre-org/prixmaroc.git /opt/prixmaroc
cd /opt/prixmaroc
```

---

## 2. Configuration des variables d'environnement

```bash
cp backend/.env.production backend/.env
nano backend/.env
```

Variables à renseigner :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `DATABASE_URL` | URL PostgreSQL async | `postgresql+asyncpg://user:pass@db:5432/prixmaroc` |
| `REDIS_URL` | URL Redis | `redis://:password@redis:6379/0` |
| `SECRET_KEY` | Clé JWT (64 chars random) | `openssl rand -hex 32` |
| `ANTHROPIC_API_KEY` | Clé API Claude | `sk-ant-...` |
| `FIREBASE_CREDENTIALS_PATH` | Chemin fichier JSON Firebase | `/app/firebase-credentials.json` |
| `SENTRY_DSN` | DSN Sentry | `https://xxx@sentry.io/xxx` |
| `CORS_ORIGINS` | Origines autorisées | `["https://votredomaine.ma"]` |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | Générer avec `openssl rand -hex 16` |
| `REDIS_PASSWORD` | Mot de passe Redis | Générer avec `openssl rand -hex 16` |

---

## 3. Configuration Firebase

1. Aller sur [Firebase Console](https://console.firebase.google.com)
2. Créer un projet → Paramètres → Comptes de service
3. Générer une clé privée → télécharger `firebase-credentials.json`
4. Copier le fichier sur le VPS :
   ```bash
   scp firebase-credentials.json user@vps:/opt/prixmaroc/backend/
   ```

---

## 4. Configuration nginx + SSL

```bash
# Modifier le domaine dans nginx/nginx.conf
nano nginx/nginx.conf
# Remplacer "votredomaine.ma" par votre vrai domaine

# Premier démarrage sans SSL (pour obtenir le certificat)
docker compose -f docker-compose.prod.yml up -d nginx certbot

# Attendre le certificat Certbot (~30 secondes)
sleep 30

# Redémarrer nginx avec SSL
docker compose -f docker-compose.prod.yml restart nginx
```

---

## 5. Déploiement complet

```bash
cd /opt/prixmaroc
chmod +x deploy.sh
./deploy.sh
```

Le script `deploy.sh` effectue automatiquement :
1. `git pull` — récupère les dernières modifications
2. Build des images Docker
3. Démarrage de PostgreSQL et Redis
4. Attente que PostgreSQL soit prêt
5. Migrations Alembic (`alembic upgrade head`)
6. Redémarrage du backend
7. Redémarrage nginx
8. Vérification santé via `/health`

---

## 6. Seed des données initiales

```bash
# Se connecter au conteneur backend
docker compose -f docker-compose.prod.yml exec backend bash

# Lancer les seeds
python seed_data.py          # Catégories + produits de base
python seed_stores_real.py   # 32 magasins réels avec GPS
```

---

## 7. Migration de base de données

```bash
# Appliquer toutes les migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Créer une nouvelle migration (depuis le conteneur)
docker compose -f docker-compose.prod.yml exec backend alembic revision --autogenerate -m "description"
```

---

## 8. Backup PostgreSQL automatique

Créer le script de backup quotidien :

```bash
cat > /opt/backup-prixmaroc.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/prixmaroc_backup_$DATE.sql.gz"

# Dump compressé
docker compose -f /opt/prixmaroc/docker-compose.prod.yml exec -T db \
  pg_dump -U prixmaroc prixmaroc | gzip > "$BACKUP_FILE"

# Upload vers Cloudflare R2 (nécessite rclone configuré)
# rclone copy "$BACKUP_FILE" r2:prixmaroc-backups/
# rm "$BACKUP_FILE"

echo "Backup créé: $BACKUP_FILE"
EOF
chmod +x /opt/backup-prixmaroc.sh

# Planifier le backup quotidien à 2h du matin
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/backup-prixmaroc.sh >> /var/log/prixmaroc-backup.log 2>&1") | crontab -
```

---

## 9. Monitoring

### UptimeRobot
1. Créer un compte sur [UptimeRobot](https://uptimerobot.com)
2. Ajouter un monitor HTTP(S) sur `https://votredomaine.ma/health`
3. Configurer les alertes email/SMS

### Sentry
1. Créer un projet Python/FastAPI sur [Sentry](https://sentry.io)
2. Copier le DSN dans `SENTRY_DSN` du fichier `.env`

---

## 10. Mise à jour de l'application

```bash
cd /opt/prixmaroc
./deploy.sh
# Les migrations sont appliquées automatiquement
```

Pour une mise à jour sans temps d'arrêt :
```bash
./deploy.sh --skip-pull  # Si vous avez déjà fait git pull manuellement
```

---

## 11. Logs et débogage

```bash
# Logs backend en temps réel
docker compose -f docker-compose.prod.yml logs -f backend

# Logs nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Statut des conteneurs
docker compose -f docker-compose.prod.yml ps

# Entrer dans le conteneur backend
docker compose -f docker-compose.prod.yml exec backend bash
```

---

## 12. Structure des services Docker

| Service | Port interne | Description |
|---------|-------------|-------------|
| `backend` | 8000 | FastAPI (Uvicorn, 2 workers) |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 (cache + queues) |
| `nginx` | 80, 443 | Reverse proxy + SSL |
| `certbot` | — | Renouvellement SSL automatique |

---

## Contacts & Support

- Documentation API : `https://votredomaine.ma/docs`
- Health check : `https://votredomaine.ma/health`
- Sentry dashboard : `https://sentry.io/organizations/votre-org/`
