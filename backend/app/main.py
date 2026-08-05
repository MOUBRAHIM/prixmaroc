import os

# Sentry optionnel — ne bloque pas le démarrage si non installé
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "development"),
            send_default_pii=False,
        )
    except ImportError:
        pass  # sentry_sdk non installé, on continue sans

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, produits, prix, magasins, listes, utilisateurs, ocr, admin_scraper, admin_products, admin_stores, admin_prices
from app.routers import api_souk
from app.routers import api_products, api_prices, api_stores, api_ai, api_dashboard, api_notifications
from app.services.scheduler import startup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — le scheduler (scraping/notifications) ne doit JAMAIS empêcher
    # l'API de démarrer : sur un hébergement contraint (peu de RAM, pas de
    # timezone système, pas de Redis) il peut échouer, l'API reste utile.
    try:
        startup_scheduler()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] Scheduler non démarré ({exc}) — l'API continue", flush=True)
    yield
    # Shutdown
    try:
        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow_credentials=False obligatoire quand allow_origins=["*"]
_cors_origins = ["*"] if settings.CORS_ALLOW_ALL else settings.cors_origins_list
_cors_credentials = not settings.CORS_ALLOW_ALL
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(utilisateurs.router)
app.include_router(produits.router)
app.include_router(prix.router)
app.include_router(magasins.router)
app.include_router(listes.router)
app.include_router(ocr.router)
app.include_router(admin_scraper.router)
app.include_router(admin_products.router)
app.include_router(admin_stores.router)
app.include_router(admin_prices.router)
app.include_router(api_products.router)
app.include_router(api_prices.router)
app.include_router(api_stores.router)
app.include_router(api_ai.router)
app.include_router(api_souk.router)
app.include_router(api_dashboard.router)
app.include_router(api_notifications.router)


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
