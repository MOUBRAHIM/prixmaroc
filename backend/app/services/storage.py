"""
Service Cloudflare R2 — Stockage des photos produits.

Cloudflare R2 est compatible avec l'API S3 (boto3).
Config requise dans .env :
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
  R2_BUCKET_NAME, R2_PUBLIC_URL
"""
from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
from pathlib import Path

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger("prixmaroc.storage")


class R2StorageService:
    """
    Upload et gestion des images produits sur Cloudflare R2.

    Fonctionnalités :
    - Upload depuis URL (scraper)
    - Upload depuis bytes (OCR / formulaire)
    - URL publique (CDN R2)
    - Vérification d'existence (évite les re-uploads)
    """

    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._bucket = settings.R2_BUCKET_NAME
        self._public_url = settings.R2_PUBLIC_URL.rstrip("/")

    # ── Upload depuis URL ─────────────────────────────────────────────────────

    async def upload_from_url(self, image_url: str, key: str | None = None) -> str | None:
        """
        Télécharge une image depuis une URL et l'upload sur R2.
        Retourne l'URL publique R2 ou None en cas d'échec.
        """
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                data = resp.content
                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        except Exception as exc:
            logger.warning(f"Échec téléchargement image {image_url}: {exc}")
            return None

        if not key:
            ext = mimetypes.guess_extension(content_type) or ".jpg"
            key = f"products/{hashlib.md5(image_url.encode()).hexdigest()}{ext}"

        return await self.upload_bytes(data, key, content_type)

    # ── Upload depuis bytes ───────────────────────────────────────────────────

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "image/jpeg",
    ) -> str | None:
        """Upload des bytes bruts sur R2. Retourne l'URL publique."""
        # Vérification d'existence (cache CDN)
        if await self.exists(key):
            logger.debug(f"[R2] Déjà présent : {key}")
            return self._public_url_for(key)

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=io.BytesIO(data),
                ContentType=content_type,
                CacheControl="public, max-age=31536000",  # 1 an
            )
            url = self._public_url_for(key)
            logger.info(f"[R2] Upload OK : {key} → {url}")
            return url
        except (BotoCoreError, ClientError) as exc:
            logger.error(f"[R2] Erreur upload {key}: {exc}")
            return None

    # ── Vérification d'existence ──────────────────────────────────────────────

    async def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise

    # ── Suppression ───────────────────────────────────────────────────────────

    async def delete(self, key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.info(f"[R2] Supprimé : {key}")
            return True
        except (BotoCoreError, ClientError) as exc:
            logger.error(f"[R2] Erreur suppression {key}: {exc}")
            return False

    # ── Listing ───────────────────────────────────────────────────────────────

    def list_keys(self, prefix: str = "products/") -> list[str]:
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            keys = []
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except (BotoCoreError, ClientError) as exc:
            logger.error(f"[R2] Erreur listing: {exc}")
            return []

    def _public_url_for(self, key: str) -> str:
        return f"{self._public_url}/{key}"


# ── Stub pour les environnements sans R2 configuré ────────────────────────────

class NoOpStorageService:
    """Remplace R2StorageService quand les credentials R2 ne sont pas fournis."""

    async def upload_from_url(self, image_url: str, key: str | None = None) -> str | None:
        logger.debug(f"[Storage NoOp] upload_from_url ignoré : {image_url}")
        return image_url  # retourne l'URL originale

    async def upload_bytes(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str | None:
        return None

    async def exists(self, key: str) -> bool:
        return False

    async def delete(self, key: str) -> bool:
        return False

    def list_keys(self, prefix: str = "products/") -> list[str]:
        return []


def get_storage_service():
    """Factory — retourne R2 si configuré, sinon NoOp."""
    if all([
        getattr(settings, "R2_ACCOUNT_ID", ""),
        getattr(settings, "R2_ACCESS_KEY_ID", ""),
        getattr(settings, "R2_SECRET_ACCESS_KEY", ""),
    ]):
        return R2StorageService()
    logger.warning("[Storage] Credentials R2 manquants → NoOpStorageService actif")
    return NoOpStorageService()
