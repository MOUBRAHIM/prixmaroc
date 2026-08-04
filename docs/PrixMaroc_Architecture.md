# Architecture Technique Complète — PrixMaroc
> Guide de référence — Étape 1.2

---

## Pourquoi FastAPI (Python) vs Node.js

Pour PrixMaroc, trois fonctionnalités critiques — OCR, scraping et machine learning — sont profondément liées à l'écosystème Python. Ce choix conditionne la maintenance de toute l'application.

| Critère | FastAPI (Python) | Node.js / Express |
|---|---|---|
| OCR / Computer Vision | ✅ Tesseract natif, OpenCV, Pillow | ❌ Bindings C++ instables |
| Scraping Scrapy | ✅ Bibliothèque native Python | ❌ Port non-officiel limité |
| Machine Learning | ✅ scikit-learn, transformers | ❌ Dépend de Python de toute façon |
| Validation API | ✅ Pydantic + Swagger auto-généré | ⚠️ Zod + swagger-jsdoc manuel |
| Performance async | ✅ ASGI / asyncio natif | ✅ Event loop V8 (égalité) |
| Écosystème IA | ✅ LangChain, Anthropic SDK | ⚠️ SDK disponible mais moins mature |
| Démarrage (cold start) | ⚠️ Plus lent qu'Express | ✅ Rapide |
| Développeurs Maroc | ⚠️ Moins commun | ✅ Plus répandu |
| **Verdict PrixMaroc** | ✅ **GAGNANT** (OCR + scraping) | ❌ Pénalise les 3 fonctions clés |

> **Conclusion :** FastAPI est retenu. Le gain sur OCR, scraping et ML compense le léger désavantage sur la disponibilité de développeurs Node.js au Maroc.

---

## 1. Diagramme d'Architecture ASCII

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  iOS App     │  │ Android App  │  │ PWA Web  │  │   Admin   │  │
│  │ React Native │  │ React Native │  │ Next.js  │  │  React    │  │
│  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └─────┬─────┘  │
└─────────┼────────────────┼──────────────┼────────────────┼─────────┘
          └────────────────┴──────────────┴────────────────┘
                                   │ HTTPS / REST + WebSocket
                   ┌───────────────▼────────────────────┐
                   │    Cloudflare CDN + WAF + DDoS     │
                   │   Rate limiting · SSL · Cache      │
                   └───────────────┬────────────────────┘
                                   │
                   ┌───────────────▼────────────────────┐
                   │  Nginx — Reverse Proxy / LB        │
                   │  /api → FastAPI  /static → R2      │
                   └──────┬──────────┬───────────┬──────┘
                          │          │           │
          ┌───────────────▼──┐  ┌────▼────┐  ┌──▼────────────────────┐
          │   FastAPI        │  │ Celery  │  │   Scraper Workers     │
          │  (Gunicorn +     │  │ Workers │  │   Scrapy + Playwright │
          │   Uvicorn)       │  │ (async) │  │   (3h du matin)       │
          │                  │  └────┬────┘  └──────────┬────────────┘
          │ /products        │       │                   │
          │ /prices          │       │                   │
          │ /ocr/scan        │       │                   │
          │ /ai/generate     │       │                   │
          │ /stores/nearby   │       │                   │
          └──┬────────┬──────┘       │                   │
             │        │              │                   │
     ┌───────▼──┐  ┌──▼───────┐     │                   │
     │PostgreSQL│  │  Redis   │◄────┘                   │
     │+ PostGIS │  │  Cache   │◄────────────────────────┘
     │ Supabase │  │  Queue   │
     └──────────┘  └──────────┘
             │
     ┌───────▼─────────────────────────────────────────────┐
     │              Services Externes                       │
     │  Google Maps API  │  Firebase FCM  │  Claude API    │
     │  Open Food Facts  │  Cloudflare R2 │  Anthropic     │
     └─────────────────────────────────────────────────────┘
```

### Flux des requêtes principales

**Scan OCR d'un ticket**
1. Mobile prend une photo → envoie image (multipart/form-data) via HTTPS
2. Cloudflare WAF → Nginx → FastAPI route `/api/ocr/scan`
3. FastAPI place la tâche dans la queue Celery (Redis broker)
4. Worker Celery : OpenCV preprocessing → Tesseract OCR → parsing
5. Résultat stocké en BDD + image sur R2 → réponse JSON au mobile
6. Mobile affiche les items détectés pour validation utilisateur

**Comparaison de prix**
1. Mobile envoie `GET /api/prices/compare?product_id=&city=Casablanca`
2. FastAPI vérifie le cache Redis (TTL 1h) — si hit : réponse < 50ms
3. Si miss : requête sur la vue `v_comparaison_prix` (PostgreSQL)
4. Résultat mis en cache Redis puis retourné au mobile

**Génération liste IA**
1. Mobile appelle `POST /api/ai/generate-list` avec type et budget
2. FastAPI récupère l'historique des 30 derniers tickets de l'utilisateur
3. Appel Claude API avec prompt contenant l'historique + profil foyer
4. Claude retourne une liste JSON structurée avec quantités et magasins
5. FastAPI enrichit avec les prix actuels → sauvegarde en BDD
6. Notification push envoyée via Firebase FCM

---

## 2. Structure des Dossiers

```
prixmaroc/                          ← Monorepo racine
├── backend/                        ← FastAPI (Python)
│   ├── app/
│   │   ├── main.py                 ← Point d'entrée FastAPI
│   │   ├── config.py               ← Settings (Pydantic BaseSettings)
│   │   ├── database.py             ← Connexion PostgreSQL (SQLAlchemy)
│   │   ├── cache.py                ← Client Redis
│   │   │
│   │   ├── models/                 ← Modèles SQLAlchemy (tables BDD)
│   │   │   ├── produit.py
│   │   │   ├── prix.py
│   │   │   ├── magasin.py
│   │   │   ├── utilisateur.py
│   │   │   ├── ticket.py
│   │   │   ├── liste.py
│   │   │   └── promotion.py
│   │   │
│   │   ├── schemas/                ← Schémas Pydantic (validation I/O)
│   │   │   ├── produit.py
│   │   │   ├── prix.py
│   │   │   ├── utilisateur.py
│   │   │   └── liste.py
│   │   │
│   │   ├── routers/                ← Endpoints API REST
│   │   │   ├── auth.py             ← /api/auth/*
│   │   │   ├── produits.py         ← /api/products/*
│   │   │   ├── prix.py             ← /api/prices/*
│   │   │   ├── magasins.py         ← /api/stores/*
│   │   │   ├── utilisateurs.py     ← /api/users/*
│   │   │   ├── listes.py           ← /api/lists/*
│   │   │   ├── ocr.py              ← /api/ocr/*
│   │   │   ├── ia.py               ← /api/ai/*
│   │   │   └── dashboard.py        ← /api/dashboard/*
│   │   │
│   │   ├── services/               ← Logique métier
│   │   │   ├── ocr_service.py      ← Tesseract + OpenCV
│   │   │   ├── scraper_service.py  ← Scrapy + Playwright
│   │   │   ├── ia_service.py       ← Claude API (recommandations)
│   │   │   ├── maps_service.py     ← Google Maps API
│   │   │   ├── notif_service.py    ← Firebase FCM
│   │   │   ├── storage_service.py  ← Cloudflare R2
│   │   │   └── prix_service.py     ← Comparaison + calcul économies
│   │   │
│   │   └── utils/
│   │       ├── security.py         ← JWT, bcrypt
│   │       ├── fuzzy_match.py      ← Matching noms produits (pg_trgm)
│   │       └── pagination.py
│   │
│   ├── scrapers/                   ← Spiders Scrapy
│   │   ├── scrapy.cfg
│   │   ├── settings.py
│   │   ├── pipelines.py            ← Dédup, BDD, R2 upload
│   │   ├── middlewares.py          ← Rate limit, rotation UA
│   │   └── spiders/
│   │       ├── marjane_spider.py
│   │       ├── carrefour_spider.py
│   │       ├── labelvie_spider.py
│   │       ├── bim_spider.py
│   │       └── generic_spider.py
│   │
│   ├── migrations/                 ← Alembic
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   │
│   ├── tests/
│   │   ├── test_ocr.py
│   │   ├── test_api_products.py
│   │   └── test_scraper.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── celery_app.py               ← Tâches async (OCR, scraping)
│
├── mobile/                         ← React Native + Expo
│   ├── App.tsx
│   ├── app.json
│   └── src/
│       ├── navigation/
│       │   └── AppNavigator.tsx    ← Tabs + Stack navigation
│       ├── screens/
│       │   ├── HomeScreen.tsx      ← Dashboard KPIs
│       │   ├── ScannerScreen.tsx   ← OCR ticket caisse
│       │   ├── ComparaisonScreen.tsx
│       │   ├── ListeAchatsScreen.tsx
│       │   ├── MagasinsScreen.tsx  ← Carte + itinéraires
│       │   └── ProfilScreen.tsx
│       ├── components/
│       │   ├── ProduitCard.tsx     ← Carte produit réutilisable
│       │   ├── PrixComparator.tsx  ← Tableau prix/magasin
│       │   ├── NutriInfo.tsx       ← Infos nutritionnelles
│       │   └── EconomiesBadge.tsx
│       ├── store/                  ← Zustand state management
│       │   ├── authStore.ts
│       │   ├── userStore.ts
│       │   └── listStore.ts
│       ├── api/                    ← Appels API (React Query)
│       │   ├── client.ts           ← Axios + interceptors JWT
│       │   ├── products.ts
│       │   ├── prices.ts
│       │   └── lists.ts
│       └── types/
│           └── index.ts
│
├── admin/                          ← Panel admin React + Vite
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Scrapers.tsx
│       │   ├── Products.tsx
│       │   └── Users.tsx
│       └── main.tsx
│
├── infrastructure/                 ← DevOps
│   ├── docker-compose.yml          ← Dev local
│   ├── docker-compose.prod.yml     ← Production
│   ├── nginx/
│   │   └── nginx.conf
│   ├── scripts/
│   │   ├── deploy.sh               ← Déploiement sans downtime
│   │   ├── backup_db.sh            ← Backup PostgreSQL → R2
│   │   └── seed_db.py              ← Données initiales (5000 produits)
│   └── .github/
│       └── workflows/
│           └── deploy.yml          ← CI/CD GitHub Actions
│
└── docs/
    ├── schema_prixmaroc.sql        ← Schéma BDD (étape 1.1)
    ├── architecture.md             ← Ce fichier
    └── api_spec.yaml               ← OpenAPI spec exportée
```

---

## 3. Variables d'Environnement

> ⚠️ **Sécurité :** Copier ce fichier vers `.env` et ne **jamais** committer `.env` dans git. Ajouter `.env` au `.gitignore` dès l'initialisation.

```bash
# ============================================================
# PRIXMAROC — Variables d'environnement (.env.example)
# ============================================================

# ── APPLICATION ──────────────────────────────────────────────
APP_ENV=development          # development | staging | production
APP_NAME=PrixMaroc
APP_VERSION=1.0.0
APP_SECRET_KEY=              # openssl rand -hex 32
DEBUG=True                   # False en production

# ── BASE DE DONNÉES PostgreSQL ────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/prixmaroc
DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/prixmaroc
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_ECHO=False                # True = log toutes les requêtes SQL

# Supabase (production)
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=                # clé service (privée)
SUPABASE_DB_URL=postgresql://postgres:pass@db.xxxx.supabase.co:5432/postgres

# ── REDIS ────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL_PRIX=3600    # 1 heure (prix actuel)
REDIS_CACHE_TTL_PRODUIT=86400 # 24 heures (données produits)
REDIS_CACHE_TTL_DASHBOARD=1800 # 30 minutes (KPIs)

# ── JWT AUTHENTIFICATION ──────────────────────────────────────
JWT_SECRET_KEY=              # openssl rand -hex 64
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE=30   # minutes
JWT_REFRESH_TOKEN_EXPIRE=30  # jours

# ── CLOUDFLARE R2 (Storage) ───────────────────────────────────
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=prixmaroc-assets
R2_PUBLIC_URL=https://assets.prixmaroc.ma
R2_FOLDER_PRODUCTS=products/
R2_FOLDER_TICKETS=tickets/
R2_FOLDER_BACKUPS=backups/

# ── GOOGLE MAPS API ───────────────────────────────────────────
GOOGLE_MAPS_API_KEY=
GOOGLE_MAPS_PLACES_ENABLED=True
GOOGLE_MAPS_DIRECTIONS_ENABLED=True
MAPS_DEFAULT_RADIUS_KM=10

# ── FIREBASE FCM (Notifications Push) ────────────────────────
FIREBASE_PROJECT_ID=prixmaroc-app
FIREBASE_CREDENTIALS_PATH=./firebase_credentials.json
FIREBASE_WEB_API_KEY=

# ── CLAUDE API (Anthropic IA) ─────────────────────────────────
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-5
CLAUDE_MAX_TOKENS=2048
CLAUDE_TEMPERATURE=0.3       # Plus bas = plus cohérent pour les listes

# ── OCR (Tesseract) ───────────────────────────────────────────
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_LANG=fra+ara       # Français + Arabe
OCR_CONFIDENCE_MIN=60        # Score minimum avant demande correction
OCR_IMAGE_MAX_SIZE_MB=10
OCR_PREPROCESS=True          # OpenCV preprocessing

# ── SCRAPING ─────────────────────────────────────────────────
SCRAPING_ENABLED=True
SCRAPING_SCHEDULE=0 3 * * *  # Cron : 3h du matin chaque jour
SCRAPING_RATE_LIMIT=0.5      # Requêtes/seconde par domaine
SCRAPING_USER_AGENT_ROTATE=True
PLAYWRIGHT_TIMEOUT=30000     # ms
SCRAPING_PROXY_URL=          # Optionnel (si IPs bloquées)

# ── OPEN FOOD FACTS API ───────────────────────────────────────
OFF_API_URL=https://world.openfoodfacts.org/api/v2
OFF_COUNTRY=morocco
OFF_FIELDS=product_name,brands,nutriments,image_url,code,categories
OFF_RATE_LIMIT=10            # requêtes/min (respecter la limite gratuite)

# ── CELERY (Task Queue) ───────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_WORKER_CONCURRENCY=4

# ── NGINX / CLOUDFLARE ───────────────────────────────────────
ALLOWED_HOSTS=prixmaroc.ma,api.prixmaroc.ma,localhost
CORS_ORIGINS=https://prixmaroc.ma,https://admin.prixmaroc.ma
CLOUDFLARE_ZONE_ID=
CLOUDFLARE_API_TOKEN=

# ── MONITORING ───────────────────────────────────────────────
SENTRY_DSN=                  # Optionnel (suivi des erreurs)
UPTIME_ROBOT_API_KEY=
LOG_LEVEL=INFO               # DEBUG | INFO | WARNING | ERROR
```

### Services nécessitant une inscription préalable

| Service | URL | Plan | Délai |
|---|---|---|---|
| Supabase (BDD) | supabase.com | Free tier | 5 min |
| Cloudflare R2 | cloudflare.com | Free (10 GB) | 10 min |
| Google Maps API | console.cloud.google.com | Pay-as-you-go | 15 min |
| Firebase FCM | console.firebase.google.com | Gratuit | 10 min |
| Anthropic Claude API | console.anthropic.com | Pay-as-you-go | 24h (review) |
| Cloudflare CDN | cloudflare.com | Free | 5 min |

---

## 4. Estimation des Coûts — 10 000 Utilisateurs

### 4.1 Détail par service

| Service | Configuration | Coût/mois | Notes |
|---|---|---|---|
| VPS OVH / DigitalOcean | 4 vCPU, 8 GB RAM, 160 GB SSD | ~400 MAD | Serveur principal (backend + nginx + Redis) |
| Supabase PostgreSQL | 500 MB DB, free tier | 0 MAD | Gratuit jusqu'à ~50K rows. Pro = ~200 MAD si dépassement |
| Cloudflare R2 Storage | 10 GB inclus gratuit | 0 MAD | Photos produits + images tickets. ~50K photos. ~9 MAD/GB au-delà |
| Cloudflare CDN + WAF | Plan Free | 0 MAD | DDoS, SSL, cache statique. Pro = ~180 MAD si WAF avancé |
| Firebase FCM | Notifications push | 0 MAD | Gratuit sans limite sur les notifs push iOS + Android |
| Google Maps API | Places + Directions | ~120 MAD | 200 USD crédit/mois offert. 10K users actifs ~60% couvert |
| Claude API (Anthropic) | ~1 000 appels/mois | ~80 MAD | Génération listes IA. 1K appels @ ~0.08 MAD/appel |
| Open Food Facts API | Données nutritionnelles | 0 MAD | API publique, gratuite, open data |
| Nom de domaine .ma | prixmaroc.ma | ~7 MAD | ~80 MAD/an. Renouvellement annuel ANRT |
| Email transactionnel | Resend (3000/mois) | 0 MAD | Confirmation, reset password |
| GitHub Actions CI/CD | 2000 min/mois gratuit | 0 MAD | ~20 déploiements/mois. Pro = ~90 MAD si dépassement |
| Monitoring | UptimeRobot (50 monitors) | 0 MAD | Alertes panne, SSL, temps de réponse |

### Total estimé : **~640 MAD/mois** pour 10 000 utilisateurs actifs

### 4.2 Évolution selon la croissance

| Palier | Volume tickets/jour | Coût/mois | Principales dépenses |
|---|---|---|---|
| 1 000 utilisateurs | < 50 | ~240 MAD | VPS 2 vCPU suffit. Tout en free tier |
| 10 000 utilisateurs | ~500 | ~640 MAD | VPS 4 vCPU requis. Google Maps sort du crédit |
| 50 000 utilisateurs | ~2 500 | ~2 200 MAD | 2 VPS. Supabase Pro. Redis dédié |
| 100 000 utilisateurs | ~5 000 | ~4 500 MAD | Load balancer + autoscaling. Équipe DevOps |

### 4.3 Optimisations pour rester dans le budget

**Redis — réduire les appels BDD**
- Cache agressif sur `prix_actuel` : TTL 1h (ne change pas souvent)
- Cache dashboard : TTL 30 min (les KPIs n'ont pas besoin d'être temps réel)
- Cache liste produits populaires : TTL 24h

**Google Maps — rester dans le crédit gratuit**
- Mettre en cache les résultats Places API (TTL 7 jours)
- Utiliser la formule Haversine pour le filtrage initial, Maps uniquement pour l'itinéraire final
- Calculer les distances en batch côté backend

**Cloudflare R2 — rester gratuit**
- Compresser les photos à 80% JPEG avant stockage (divise le volume par 3)
- Générer une miniature 200x200 au moment du upload
- Supprimer les images tickets OCR après 30 jours

---

## 5. Démarrage Rapide

### 5.1 Lancer l'environnement local

```bash
# 1. Cloner le repo
git clone https://github.com/ton-org/prixmaroc.git && cd prixmaroc

# 2. Copier les variables d'environnement
cp backend/.env.example backend/.env
# Éditer backend/.env avec tes clés API

# 3. Lancer tous les services (BDD + Redis + Backend + Workers)
docker-compose up -d

# 4. Jouer les migrations Alembic
docker-compose exec backend alembic upgrade head

# 5. Seed de la base de données (5000 produits depuis Open Food Facts)
docker-compose exec backend python infrastructure/scripts/seed_db.py

# API accessible sur :
# http://localhost:8000/docs   ← Swagger UI interactif
# http://localhost:8000/redoc  ← Documentation ReDoc
```

### 5.2 Lancer l'app mobile

```bash
cd mobile
npm install
npx expo start
# Scanner le QR code avec l'app Expo Go sur ton téléphone
# iOS: App Store → "Expo Go"   |   Android: Play Store → "Expo Go"
```

### 5.3 Vérifier que tout fonctionne

| Test | URL / Commande | Résultat attendu |
|---|---|---|
| API Health | `GET /health` | `{ status: "ok", db: "connected", redis: "connected" }` |
| Swagger UI | `http://localhost:8000/docs` | Interface avec tous les endpoints |
| PostgreSQL | `docker-compose exec db psql -U prixmaroc -c '\dt'` | Liste des 18 tables |
| Redis | `docker-compose exec redis redis-cli ping` | `PONG` |
| OCR test | `POST /api/ocr/scan` + image | JSON avec produits parsés |
| API Produits | `GET /api/products?search=lait` | Liste produits avec prix |

---

## Prochaines étapes

> ✅ **Étape 1.2 terminée.** L'architecture est validée. Passe à l'**Étape 2.1** dans Claude Code.

| Étape | Description | Outil | Durée |
|---|---|---|---|
| 2.1 | Initialisation projet FastAPI + Docker-compose | Claude Code | 2-3h |
| 2.2 | Service OCR — lecture tickets marocains | Claude Code | 1 journée |
| 2.3 | Service de scraping GMS (Marjane, Carrefour…) | Claude Code | 1 semaine |
| 2.4 | API REST complète (produits, prix, magasins) | Claude Code | 1 semaine |
| 3.1 | Moteur de recommandations IA (Claude API) | Claude Code | 1 semaine |
| 4.1 | Frontend React Native — setup complet | Claude Code | 2-3h |
