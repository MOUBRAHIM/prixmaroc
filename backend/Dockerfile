FROM python:3.12-slim

# ── Dépendances système ────────────────────────────────────────────────────────
# • build-essential / libpq-dev  : compilation asyncpg / psycopg2
# • tesseract-ocr + langues      : OCR français + arabe
# • poppler-utils                : pdf2image (conversion PDF → images)
# • libgl1                       : OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-ara \
    # PDF → images
    poppler-utils \
    # OpenCV
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dépendances Python ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Code source ───────────────────────────────────────────────────────────────
COPY . .

EXPOSE 8000

# Migrations Alembic puis démarrage uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
