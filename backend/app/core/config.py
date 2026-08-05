import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "PrixMaroc API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://prixmaroc:prixmaroc@db:5432/prixmaroc"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 jours

    # External APIs (optionnels)
    GOOGLE_MAPS_KEY: str = ""
    GOOGLE_VISION_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Cloudflare R2 (stockage images scraper)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "prixmaroc-images"
    R2_PUBLIC_URL: str = ""

    # CORS — champ str (et non list) pour éviter le parsing JSON auto de
    # pydantic-settings qui plante sur "*". On accepte : "*", une liste JSON
    # ["..."], ou des valeurs séparées par virgules. Voir cors_origins_list.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    CORS_ALLOW_ALL: bool = False  # True si CORS_ORIGINS contient "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS en liste, quel que soit le format fourni."""
        s = (self.CORS_ORIGINS or "").strip()
        if s == "" or s == "*":
            return ["*"]
        if s.startswith("["):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        return [o.strip() for o in s.split(",") if o.strip()]

    def model_post_init(self, __context):  # type: ignore[override]
        # Nettoyage : un copier-coller depuis un tableau/navigateur peut ajouter
        # une tabulation, un espace ou des guillemets autour de l'URL, ce qui
        # rend l'URL impossible à parser par SQLAlchemy.
        db_url = (self.DATABASE_URL or "").strip().strip('"').strip("'").strip()
        # Railway fournit postgresql:// → psycopg3 async pour SQLAlchemy
        if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        object.__setattr__(self, "DATABASE_URL", db_url)
        # CORS wildcard
        if "*" in self.cors_origins_list:
            object.__setattr__(self, "CORS_ALLOW_ALL", True)


settings = Settings()
