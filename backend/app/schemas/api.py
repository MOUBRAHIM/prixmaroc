"""
Schemas de réponse enrichis pour les routers API publics.
Séparés des schemas CRUD de base pour ne pas les polluer.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────────────

class PageMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


class Paginated[T](BaseModel):
    data: list[T]
    meta: PageMeta


# ──────────────────────────────────────────────────────────────────────────────
# Produits
# ──────────────────────────────────────────────────────────────────────────────

class PriceInStore(BaseModel):
    store_id: int
    store_name: str
    store_city: str | None
    store_logo: str | None
    price: float
    currency: str
    is_promo: bool
    promo_price: float | None
    effective_price: float          # promo_price si promo sinon price
    source: str | None = None       # "scraper" | "ocr" | "manual"
    recorded_at: datetime


class ProductSummary(BaseModel):
    id: int
    name: str
    slug: str
    brand: str | None
    image_url: str | None
    unit_size: str | None
    category_name: str | None
    lowest_price: float | None
    highest_price: float | None
    store_count: int
    has_promo: bool = False


class ProductDetail(BaseModel):
    id: int
    name: str
    slug: str
    barcode: str | None
    brand: str | None
    description: str | None
    image_url: str | None
    unit: str | None
    unit_size: str | None
    category_name: str | None
    prices: list[PriceInStore]
    lowest_price: float | None
    highest_price: float | None
    average_price: float | None
    store_count: int
    # Infos nutritionnelles (pour 100g)
    calories: float | None = None
    proteins: float | None = None
    lipids: float | None = None
    carbs: float | None = None
    fibers: float | None = None
    nutriscore: str | None = None


class PricePoint(BaseModel):
    """Un point de l'historique des prix."""
    date: str           # "YYYY-MM-DD"
    price: float
    store_id: int
    store_name: str
    is_promo: bool


class PriceHistory(BaseModel):
    product_id: int
    product_name: str
    days: int
    points: list[PricePoint]
    min_price: float | None
    max_price: float | None
    avg_price: float | None


class CompareProduct(BaseModel):
    product: ProductDetail
    cheapest_store: str | None
    savings_vs_max: float | None    # économie possible en MAD


class CompareResponse(BaseModel):
    products: list[CompareProduct]
    common_stores: list[str]        # magasins qui ont tous les produits


# ──────────────────────────────────────────────────────────────────────────────
# Prix
# ──────────────────────────────────────────────────────────────────────────────

class CheapestPrice(BaseModel):
    store_id: int
    store_name: str
    store_city: str | None
    store_lat: float | None
    store_lng: float | None
    price: float
    is_promo: bool
    promo_price: float | None
    effective_price: float
    recorded_at: datetime
    savings_vs_avg: float | None    # économie vs prix moyen (MAD)
    savings_pct: float | None       # économie en %


class CheapestResponse(BaseModel):
    product_id: int
    product_name: str
    city: str | None
    results: list[CheapestPrice]
    average_price: float | None


class PromoItem(BaseModel):
    product_id: int
    product_name: str
    product_image: str | None
    store_id: int
    store_name: str
    store_city: str | None
    regular_price: float
    promo_price: float
    discount_pct: float             # pourcentage de réduction
    promo_end: str | None           # date de fin de promo
    recorded_at: datetime


class PromosResponse(BaseModel):
    city: str | None
    count: int
    promotions: list[PromoItem]


# ──────────────────────────────────────────────────────────────────────────────
# Magasins
# ──────────────────────────────────────────────────────────────────────────────

class StoreNearby(BaseModel):
    id: int
    name: str
    slug: str
    address: str | None
    city: str | None
    latitude: float | None
    longitude: float | None
    logo_url: str | None
    distance_km: float | None       # calculé depuis le point de référence
    product_count: int | None


class RouteStop(BaseModel):
    order: int
    store_id: int
    store_name: str
    store_address: str | None
    latitude: float | None
    longitude: float | None
    products_to_buy: list[str]      # noms des produits les moins chers ici
    estimated_savings: float        # économies réalisées dans ce magasin


class RouteOptimizeResponse(BaseModel):
    """
    Résultat de l'optimisation de parcours multi-magasins.
    Algorithme : greedy nearest-neighbor (approximation TSP).
    """
    stops: list[RouteStop]
    total_stores: int
    total_distance_km: float | None
    total_savings: float
    algorithm: str = "nearest-neighbor"


class StoreProductSummary(BaseModel):
    product_id: int
    product_name: str
    product_image: str | None
    price: float
    is_promo: bool
    promo_price: float | None
    effective_price: float
    recorded_at: datetime
