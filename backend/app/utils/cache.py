"""
Utilitaire Cache Redis pour PrixMaroc.

Usage :
    cache = RedisCache()

    # Décorateur automatique
    @cache.cached(ttl=3600, key_prefix="product")
    async def get_product(product_id: int): ...

    # API manuelle
    data = await cache.get("my_key")
    await cache.set("my_key", data, ttl=3600)
    await cache.delete("my_key")
    await cache.invalidate_prefix("product:")
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Callable

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("prixmaroc.cache")

# TTL standards (secondes)
TTL_PRICES   = 3_600       # 1 heure
TTL_PRODUCTS = 86_400      # 24 heures
TTL_STORES   = 86_400      # 24 heures
TTL_SHORT    = 300         # 5 minutes (promotions, résultats volatils)


class RedisCache:
    """Wrapper Redis asynchrone avec sérialisation JSON et gestion d'erreurs."""

    def __init__(self):
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._client

    # ── Opérations de base ────────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self.client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning(f"[Cache] GET '{key}' échoué : {exc}")
            return None

    async def set(self, key: str, value: Any, ttl: int = TTL_PRODUCTS) -> bool:
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            await self.client.setex(key, ttl, serialized)
            return True
        except Exception as exc:
            logger.warning(f"[Cache] SET '{key}' échoué : {exc}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            await self.client.delete(key)
            return True
        except Exception as exc:
            logger.warning(f"[Cache] DELETE '{key}' échoué : {exc}")
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Supprime toutes les clés commençant par `prefix`."""
        try:
            keys = await self.client.keys(f"{prefix}*")
            if keys:
                await self.client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning(f"[Cache] INVALIDATE '{prefix}*' échoué : {exc}")
            return 0

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self.client.exists(key))
        except Exception:
            return False

    async def ttl(self, key: str) -> int:
        """Retourne le TTL restant en secondes (-1 = pas d'expiration, -2 = absent)."""
        try:
            return await self.client.ttl(key)
        except Exception:
            return -2

    # ── Décorateur ────────────────────────────────────────────────────────────

    def cached(self, ttl: int = TTL_PRODUCTS, key_prefix: str = "cache"):
        """
        Décorateur pour mettre en cache le résultat d'une coroutine async.

        La clé est construite à partir du préfixe + MD5 des arguments sérialisés.

        Exemple :
            @cache.cached(ttl=TTL_PRICES, key_prefix="cheapest")
            async def get_cheapest(product_id: int, city: str | None): ...
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Génération de la clé
                cache_key = self._make_key(key_prefix, args, kwargs)

                # Tentative de lecture
                cached = await self.get(cache_key)
                if cached is not None:
                    logger.debug(f"[Cache] HIT {cache_key}")
                    return cached

                # Exécution de la fonction
                result = await func(*args, **kwargs)

                # Mise en cache (uniquement si le résultat n'est pas None)
                if result is not None:
                    await self.set(cache_key, result, ttl=ttl)
                    logger.debug(f"[Cache] SET {cache_key} (TTL={ttl}s)")

                return result
            return wrapper
        return decorator

    @staticmethod
    def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
        payload = json.dumps({"a": args, "k": kwargs}, default=str, sort_keys=True)
        digest = hashlib.md5(payload.encode()).hexdigest()[:12]
        return f"prixmaroc:{prefix}:{digest}"


# Singleton partagé
cache = RedisCache()


# ── Helpers pour les routers ──────────────────────────────────────────────────

def make_product_key(product_id: int) -> str:
    return f"prixmaroc:product:{product_id}"

def make_search_key(query: str, category_id: int | None, city: str | None,
                    skip: int, limit: int) -> str:
    raw = f"{query}:{category_id}:{city}:{skip}:{limit}"
    return f"prixmaroc:products:search:{hashlib.md5(raw.encode()).hexdigest()[:12]}"

def make_prices_key(product_id: int, city: str | None) -> str:
    return f"prixmaroc:prices:{product_id}:{city or 'all'}"

def make_history_key(product_id: int, days: int) -> str:
    return f"prixmaroc:history:{product_id}:{days}"

def make_promotions_key(city: str | None) -> str:
    return f"prixmaroc:promos:{city or 'all'}"

def make_stores_key(lat: float, lng: float, radius: float) -> str:
    return f"prixmaroc:stores:nearby:{lat:.3f}:{lng:.3f}:{radius}"

def make_store_products_key(store_id: int, skip: int, limit: int) -> str:
    return f"prixmaroc:store:{store_id}:products:{skip}:{limit}"

import hashlib  # noqa: E402 (déjà importé via make_key, redéclaré pour clarté)
