"""
Service de scraping éthique — Catalogues GMS marocains.

Architecture :
  EthicalScraperBase          Socle commun (robots.txt, rate limit, UA rotation, CAPTCHA)
    ├── MarjaneScraper         marjane.ma
    ├── CarrefourScraper       carrefour.ma
    ├── LabelVieScraper        labelvie.ma
    ├── BimScraper             bim.ma
    ├── KazyonScraper          kazyon.com/ma
    ├── SoprecoScraper         sopreco.ma (Atacadão)
    ├── HmizateScraper         hmizate.ma (agrégateur bons plans)
    └── GenericScraper         configurable via admin (sélecteurs CSS)

  ScraperOrchestrator         Orchestre les scrapers + déduplication + logs BDD
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import AsyncIterator
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("prixmaroc.scraper")


# ──────────────────────────────────────────────────────────────────────────────
# Structures de données
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ScrapedProduct:
    name: str
    price: float
    currency: str = "MAD"
    category: str | None = None
    image_url: str | None = None
    image_local_url: str | None = None   # après upload R2
    barcode: str | None = None
    unit: str | None = None
    brand: str | None = None
    source_url: str = ""
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Fingerprint pour la déduplication
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            raw = f"{self.name.lower().strip()}{self.price}"
            self.fingerprint = hashlib.md5(raw.encode()).hexdigest()


@dataclass
class ScrapeResult:
    config_slug: str
    products: list[ScrapedProduct] = field(default_factory=list)
    pages_scraped: int = 0
    captcha_hits: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


# ──────────────────────────────────────────────────────────────────────────────
# User-Agent pool
# ──────────────────────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# Indicateurs de CAPTCHA dans le HTML
CAPTCHA_SIGNALS = [
    "captcha", "recaptcha", "hcaptcha", "cf-challenge",
    "robot", "verify you are human", "access denied",
    "403 forbidden", "too many requests", "rate limit",
    "cloudflare", "ddos-guard", "bot detection",
]


# ──────────────────────────────────────────────────────────────────────────────
# 1. Base — Scraper éthique
# ──────────────────────────────────────────────────────────────────────────────

class EthicalScraperBase:
    """
    Fonctionnalités communes à tous les scrapers :
    - Vérification robots.txt (avec cache 24h)
    - Rate limiting par domaine (token bucket)
    - Rotation automatique des User-Agents
    - Détection et gestion des CAPTCHAs
    - Retry exponentiel avec jitter
    - Logging structuré
    """

    RATE_LIMIT_SECONDS: float = 2.0      # délai minimum entre 2 requêtes
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: float = 15.0
    CAPTCHA_PAUSE_SECONDS: float = 300.0  # pause 5 min en cas de CAPTCHA

    def __init__(self, rate_limit: float | None = None):
        self._rate_limit = rate_limit or self.RATE_LIMIT_SECONDS
        self._last_request: dict[str, float] = {}   # domaine → timestamp
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._session: httpx.AsyncClient | None = None
        self._captcha_callback: callable | None = None

    # ── Session HTTP ──────────────────────────────────────────────────────────

    async def __aenter__(self) -> "EthicalScraperBase":
        self._session = httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=self._base_headers(),
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._session:
            await self._session.aclose()

    def _base_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def on_captcha(self, callback: callable) -> None:
        """Enregistre un callback appelé lors d'un CAPTCHA (pour alerter l'admin)."""
        self._captcha_callback = callback

    # ── Robots.txt ────────────────────────────────────────────────────────────

    async def _can_fetch(self, url: str) -> bool:
        """Vérifie si robots.txt autorise le scraping de cette URL."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self._robots_cache:
            robots_url = f"{base}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                if self._session:
                    resp = await self._session.get(robots_url)
                    rp.parse(resp.text.splitlines())
                else:
                    rp.read()
            except Exception:
                # Si robots.txt inaccessible → on considère autorisé
                pass
            self._robots_cache[base] = rp

        rp = self._robots_cache[base]
        ua = self._session.headers.get("User-Agent", "*") if self._session else "*"
        return rp.can_fetch(ua, url)

    # ── Rate limiting ─────────────────────────────────────────────────────────

    async def _rate_limit_wait(self, url: str) -> None:
        """Attend le temps nécessaire pour respecter le rate limit par domaine."""
        domain = urlparse(url).netloc
        last = self._last_request.get(domain, 0.0)
        elapsed = time.monotonic() - last
        wait = self._rate_limit - elapsed
        if wait > 0:
            # Ajoute un jitter aléatoire (±20%) pour être moins prévisible
            jitter = random.uniform(-0.2 * wait, 0.2 * wait)
            await asyncio.sleep(wait + jitter)
        self._last_request[domain] = time.monotonic()

    # ── Requête principale ────────────────────────────────────────────────────

    async def fetch(self, url: str, run_log: list[str] | None = None) -> str | None:
        """
        Récupère le HTML d'une URL avec :
        - vérification robots.txt
        - rate limiting
        - rotation UA
        - retry exponentiel
        - détection CAPTCHA
        """
        if not await self._can_fetch(url):
            msg = f"[robots.txt] Accès refusé : {url}"
            logger.warning(msg)
            if run_log is not None:
                run_log.append(msg)
            return None

        await self._rate_limit_wait(url)

        # Rotation UA à chaque requête
        if self._session:
            self._session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = await self._session.get(url)

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited → attente {wait}s ({url})")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code in (403, 503):
                    html = resp.text.lower()
                    if self._is_captcha(html):
                        await self._handle_captcha(url, run_log)
                        return None
                    logger.warning(f"HTTP {resp.status_code} : {url}")
                    return None

                resp.raise_for_status()
                html = resp.text

                if self._is_captcha(html.lower()):
                    await self._handle_captcha(url, run_log)
                    return None

                return html

            except httpx.TimeoutException:
                backoff = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"Timeout (tentative {attempt}/{self.MAX_RETRIES}) → retry dans {backoff:.1f}s")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(backoff)

            except httpx.RequestError as exc:
                logger.error(f"Erreur réseau : {exc}")
                return None

        logger.error(f"Échec après {self.MAX_RETRIES} tentatives : {url}")
        return None

    def _is_captcha(self, html_lower: str) -> bool:
        return any(sig in html_lower for sig in CAPTCHA_SIGNALS)

    async def _handle_captcha(self, url: str, run_log: list[str] | None) -> None:
        msg = f"[CAPTCHA] Détecté sur {url} — pause {self.CAPTCHA_PAUSE_SECONDS}s"
        logger.error(msg)
        if run_log is not None:
            run_log.append(msg)
        if self._captcha_callback:
            await self._captcha_callback(url)
        await asyncio.sleep(self.CAPTCHA_PAUSE_SECONDS)

    # ── Parser HTML ───────────────────────────────────────────────────────────

    @staticmethod
    def _soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def _price(text: str) -> float | None:
        """Extrait un prix MAD depuis un texte ('12.50 MAD', '12,50 Dhs', etc.)."""
        m = re.search(r"(\d{1,5}[.,]\d{2})", text.replace("\xa0", "").replace(" ", ""))
        if m:
            return float(m.group(1).replace(",", "."))
        m = re.search(r"(\d{1,5})", text)
        return float(m.group(1)) if m else None


# ──────────────────────────────────────────────────────────────────────────────
# 2. Scraper Marjane
# ──────────────────────────────────────────────────────────────────────────────

class MarjaneScraper(EthicalScraperBase):
    """
    Scrape les catalogues produits de marjane.ma.

    Structure HTML cible (schema.org Product) :
      .product-item
        .product-item-name   → nom
        .price               → prix
        .product-image img   → photo
        [data-category]      → catégorie
    """
    BASE_URL = "https://www.marjane.ma"
    CATALOG_URLS = [
        "/fr/alimentation",
        "/fr/boissons",
        "/fr/produits-frais",
        "/fr/epicerie",
        "/fr/hygiene-beaute",
        "/fr/entretien-maison",
    ]

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="marjane")
        async with self:
            for path in self.CATALOG_URLS:
                url = self.BASE_URL + path
                page = 1
                while True:
                    paginated = f"{url}?p={page}"
                    logger.info(f"[Marjane] Scrape : {paginated}")
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break

                    products, has_next = self._parse_page(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1

                    if not has_next or page > 50:
                        break
                    page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_page(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        for item in soup.select(".product-item, [data-product-id], .product-card"):
            name_el  = item.select_one(".product-item-name, .product-name, h2.name, .name")
            price_el = item.select_one(".price, .product-price, [data-price]")
            img_el   = item.select_one("img.product-image-photo, img[data-src], img.product-img")
            cat_el   = item.select_one("[data-category], .category-name")

            if not name_el or not price_el:
                continue

            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("data-src") or img_el.get("src")
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one("a.next, a[rel=next], .pagination .next:not(.disabled)"))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 3. Scraper Carrefour Maroc
# ──────────────────────────────────────────────────────────────────────────────

class CarrefourScraper(EthicalScraperBase):
    """
    Scrape carrefour.ma — utilise souvent une API JSON interne.

    Deux stratégies :
      1. API JSON /api/products (si disponible)
      2. Fallback HTML avec sélecteurs CSS
    """
    BASE_URL = "https://www.carrefour.ma"
    API_BASE  = "https://www.carrefour.ma/api/catalog_chunk/en"
    CATALOG_PATHS = [
        "/fr/alimentation",
        "/fr/boissons-jus",
        "/fr/produits-frais-surgeles",
        "/fr/hygiene-et-beaute",
        "/fr/entretien",
    ]

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="carrefour")
        async with self:
            for path in self.CATALOG_PATHS:
                url = self.BASE_URL + path
                page = 0
                while True:
                    # Tente d'abord l'API JSON
                    api_url = f"{self.API_BASE}{path}?from={page * 24}&size=24"
                    html = await self.fetch(api_url, run_log)

                    if html:
                        try:
                            import json
                            data = json.loads(html)
                            products = self._parse_api(data, url)
                            if not products:
                                break
                            result.products.extend(products)
                            result.pages_scraped += 1
                            page += 1
                            continue
                        except Exception:
                            pass

                    # Fallback HTML
                    paginated = f"{url}?page={page + 1}"
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break
                    products, has_next = self._parse_html(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1
                    if not has_next or page > 50:
                        break
                    page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_api(self, data: dict | list, source_url: str) -> list[ScrapedProduct]:
        products = []
        items = data if isinstance(data, list) else data.get("products", data.get("items", []))
        for item in items:
            name  = item.get("name") or item.get("title")
            price = item.get("price") or item.get("selling_price")
            if not name or price is None:
                continue
            try:
                price_val = float(str(price).replace(",", "."))
            except ValueError:
                continue
            products.append(ScrapedProduct(
                name=name,
                price=price_val,
                category=item.get("category_name") or item.get("category"),
                image_url=item.get("image_url") or item.get("thumbnail"),
                barcode=str(item.get("ean") or item.get("barcode") or ""),
                brand=item.get("brand"),
                source_url=source_url,
            ))
        return products

    def _parse_html(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        for item in soup.select(".product-item, .product-card, [data-testid='product-card']"):
            name_el  = item.select_one(".product-name, h3, .title, [data-testid='product-name']")
            price_el = item.select_one(".price, .product-price, [data-testid='product-price']")
            img_el   = item.select_one("img")
            cat_el   = item.select_one(".category, .breadcrumb-item:last-child")

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("src") or img_el.get("data-src")
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one("a[rel=next], .pagination .next:not(.disabled), [aria-label='Next page']"))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 4. Scraper Label'Vie
# ──────────────────────────────────────────────────────────────────────────────

class LabelVieScraper(EthicalScraperBase):
    """Scrape labelvie.ma — site Magento/Prestashop."""
    BASE_URL = "https://www.labelvie.ma"
    CATALOG_PATHS = [
        "/alimentation",
        "/boissons",
        "/surgeles-frais",
        "/hygiene-beaute",
        "/entretien",
        "/epicerie",
    ]

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="labelvie")
        async with self:
            for path in self.CATALOG_PATHS:
                url = self.BASE_URL + path
                page = 1
                while True:
                    paginated = f"{url}?page={page}"
                    logger.info(f"[Label'Vie] Scrape : {paginated}")
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break

                    products, has_next = self._parse_page(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1

                    if not has_next or page > 50:
                        break
                    page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_page(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        for item in soup.select(".product-miniature, .product-item, article.product"):
            name_el  = item.select_one(".product-title, h2, h3, .name")
            price_el = item.select_one(".product-price, .price, span.price")
            img_el   = item.select_one("img.product-img, img[loading='lazy'], img")
            cat_el   = soup.select_one("h1.page-heading, .category-sub-menu .current")

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = (img_el.get("data-src") or img_el.get("src", "")).strip()
                if img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url or None,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one("a[rel=next], .next a, .pagination li.next:not(.disabled) a"))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 5. Scraper BIM Maroc
# ──────────────────────────────────────────────────────────────────────────────

class BimScraper(EthicalScraperBase):
    """
    Scrape bim.ma — chaîne discount turque implantée au Maroc.

    Le site BIM publie des catalogues PDF hebdomadaires + une page produits.
    Structure HTML :
      .product-box / .product-card
        .product-title / h3       → nom
        .product-price / .price   → prix
        img                       → photo
        .product-category         → catégorie

    Note: BIM ne dispose pas de rayon boucherie fraîche.
    Les produits viande fraîche/boucherie sont filtrés automatiquement.
    """
    BASE_URL = "https://www.bim.ma"
    CATALOG_URLS = [
        "/fr/produits/alimentation",
        "/fr/produits/boissons",
        "/fr/produits/hygiene-beaute",
        "/fr/produits/entretien",
        "/fr/produits/frais",
        "/fr/promotions",
    ]

    # BIM ne vend pas de viande fraîche de boucherie — on exclut ces produits
    _EXCL_NAME_RE = re.compile(
        r"\b(boucherie|viande\s+fra[iî]che|agneau\s+entier|gigot\b|c[oô]telette"
        r"|selle\s+d|kefta\s+fra[iî]che|merguez\s+fra[iî]che|foie\s+de\s+veau"
        r"|r[oô]ti\s+de|jarret|bavette|entrecôte|entrecote|côte\s+de\s+b[oœ]uf"
        r"|cote\s+de\s+boeuf|filet\s+de\s+b[oœ]uf)\b",
        re.IGNORECASE,
    )
    _EXCL_CAT_RE = re.compile(
        r"\b(boucherie|viandes?\s+fra[iî]ches?|rayon\s+viande)\b",
        re.IGNORECASE,
    )

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="bim")
        async with self:
            for path in self.CATALOG_URLS:
                url = self.BASE_URL + path
                page = 1
                while True:
                    paginated = f"{url}?page={page}"
                    logger.info(f"[BIM] Scrape : {paginated}")
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break
                    products, has_next = self._parse_page(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1
                    if not has_next or page > 50:
                        break
                    page += 1
        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_page(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        for item in soup.select(".product-box, .product-card, .product-item, article.product"):
            name_el  = item.select_one(".product-title, h3, h2, .title, .name")
            price_el = item.select_one(".product-price, .price, .prix, [class*='price']")
            img_el   = item.select_one("img")
            cat_el   = item.select_one(".product-category, .category")

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            # Filtre : BIM ne vend pas de viande fraîche de boucherie
            name_text = name_el.get_text(strip=True)
            cat_text  = cat_el.get_text(strip=True) if cat_el else ""
            if self._EXCL_NAME_RE.search(name_text) or self._EXCL_CAT_RE.search(cat_text):
                logger.debug(f"[BIM] Produit exclu (viande) : {name_text!r}")
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("data-src") or img_el.get("src")
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one("a[rel=next], .pagination .next:not(.disabled), a.next"))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 6. Scraper Kazyon Maroc
# ──────────────────────────────────────────────────────────────────────────────

class KazyonScraper(EthicalScraperBase):
    """
    Scrape kazyon.com/ma — chaîne discount égyptienne présente au Maroc.

    Kazyon utilise souvent un site React/Next.js avec une API JSON interne.
    Deux stratégies :
      1. API JSON /api/v1/products (si disponible)
      2. Fallback HTML classique
    """
    BASE_URL = "https://www.kazyon.com"
    API_BASE  = "https://www.kazyon.com/api/v1"
    CATALOG_PATHS = [
        "/ma/alimentation",
        "/ma/boissons",
        "/ma/hygiene",
        "/ma/entretien",
        "/ma/epicerie",
        "/ma/promotions",
    ]

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="kazyon")
        async with self:
            for path in self.CATALOG_PATHS:
                url = self.BASE_URL + path
                page = 1
                while True:
                    # Tentative API JSON Next.js
                    api_url = f"{self.API_BASE}/products?country=ma&category={path.split('/')[-1]}&page={page}&limit=24"
                    html = await self.fetch(api_url, run_log)
                    if html:
                        try:
                            import json
                            data = json.loads(html)
                            products = self._parse_api(data, url)
                            if products:
                                result.products.extend(products)
                                result.pages_scraped += 1
                                page += 1
                                continue
                        except Exception:
                            pass

                    # Fallback HTML
                    paginated = f"{url}?page={page}"
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break
                    products, has_next = self._parse_html(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1
                    if not has_next or page > 50:
                        break
                    page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_api(self, data: dict | list, source_url: str) -> list[ScrapedProduct]:
        products = []
        items = data if isinstance(data, list) else data.get("data", data.get("products", []))
        for item in items:
            name  = item.get("name") or item.get("nameAr") or item.get("title")
            price = item.get("price") or item.get("sellingPrice") or item.get("priceAfterDiscount")
            if not name or price is None:
                continue
            try:
                price_val = float(str(price).replace(",", "."))
            except ValueError:
                continue
            products.append(ScrapedProduct(
                name=name,
                price=price_val,
                category=item.get("category") or item.get("categoryName"),
                image_url=item.get("image") or item.get("imageUrl") or item.get("thumbnail"),
                barcode=str(item.get("barcode") or item.get("sku") or ""),
                brand=item.get("brand"),
                source_url=source_url,
            ))
        return products

    def _parse_html(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        for item in soup.select(".product, .product-card, [class*='ProductCard'], [class*='product-item']"):
            name_el  = item.select_one("[class*='name'], [class*='title'], h2, h3")
            price_el = item.select_one("[class*='price'], [class*='Price']")
            img_el   = item.select_one("img")
            cat_el   = soup.select_one("h1, [class*='category-title']")

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("src") or img_el.get("data-src")
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one("a[rel=next], [class*='next']:not([class*='disabled'])"))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 7. Scraper Sopreco (Atacadão / Épiceries Sopreco)
# ──────────────────────────────────────────────────────────────────────────────

class SoprecoScraper(EthicalScraperBase):
    """
    Scrape le catalogue Sopreco — grossiste/distributeur marocain.

    Sopreco opère aussi sous l'enseigne Atacadão au Maroc.
    Site souvent basé sur Prestashop ou Woocommerce.
    """
    BASE_URL = "https://www.sopreco.ma"
    CATALOG_URLS = [
        "/alimentation",
        "/boissons",
        "/produits-laitiers",
        "/hygiene-beaute",
        "/entretien-menager",
        "/epicerie-salee",
        "/promotions",
    ]

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="sopreco")
        async with self:
            for path in self.CATALOG_URLS:
                url = self.BASE_URL + path
                page = 1
                while True:
                    paginated = f"{url}?page={page}"
                    logger.info(f"[Sopreco] Scrape : {paginated}")
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break
                    products, has_next = self._parse_page(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1
                    if not has_next or page > 50:
                        break
                    page += 1
        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse_page(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []

        # Prestashop — sélecteurs standard
        for item in soup.select(
            ".product-miniature, .product_list article, "
            ".product-container, .product-item, .js-product"
        ):
            name_el  = item.select_one(".product-title a, h2, h3, .product-name")
            price_el = item.select_one(".product-price, .price, .regular-price, .our_price_display")
            img_el   = item.select_one("img.product-cover-img, img[loading='lazy'], img")
            cat_el   = soup.select_one("h1.page-heading, .category-sub-menu .current, .breadcrumb li:last-child")

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("data-src") or img_el.get("src")
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one(
            "a[rel=next], .next a, #pagination_next a, "
            ".pagination li.next:not(.disabled) a"
        ))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 8. Scraper Hmizate.ma
# ──────────────────────────────────────────────────────────────────────────────

class HmizateScraper(EthicalScraperBase):
    """
    Scrape hmizate.ma — agrégateur de bons plans / catalogues promotionnels marocains.

    Le site liste les offres flash et catalogues de BIM, Marjane, Carrefour, etc.
    Structure cible (cover plusieurs variantes du site) :

      Article deal / bon plan :
        .deal-card / .product / .offer-item / article
          .deal-title / .product-name / h2 / h3  → nom produit
          .deal-price / .price / .promo-price     → prix promo
          .old-price / .original-price            → (optionnel) ancien prix
          img                                     → photo
          .deal-store / .store-name               → enseigne

    Stratégie :
      1. Initialisation session (GET homepage → cookies)
      2. Parcours des catégories produits
      3. Tentative API JSON interne (/api/deals, /api/products)
      4. Fallback scraping HTML classique
    """

    BASE_URL   = "https://hmizate.ma"
    RATE_LIMIT_SECONDS = 3.0          # site léger, on reste courtois

    # Catégories connues sur hmizate.ma (slugs observés)
    CATEGORY_PATHS = [
        "/bons-plans/alimentaire",
        "/bons-plans/epicerie",
        "/bons-plans/hygiene-beaute",
        "/bons-plans/entretien-maison",
        "/bons-plans/boissons",
        "/bons-plans/frais-surgeles",
        "/bons-plans/boucherie-charcuterie",
        "/promotions",
        "/catalogues",
    ]

    # Endpoints API JSON à essayer avant le fallback HTML
    API_ENDPOINTS = [
        "/api/deals",
        "/api/products",
        "/api/offers",
        "/api/v1/deals",
        "/api/v1/products",
    ]

    def _base_headers(self) -> dict:
        """Headers très proches d'un vrai navigateur Chrome pour éviter le 403."""
        ua = random.choice(USER_AGENTS)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "fr-MA,fr;q=0.9,ar-MA;q=0.8,ar;q=0.7,en-US;q=0.6,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _init_session(self) -> None:
        """Visite la homepage pour obtenir les cookies de session."""
        try:
            resp = await self._session.get(self.BASE_URL + "/")
            logger.info(f"[Hmizate] Session initialisée (HTTP {resp.status_code})")
            # Mise à jour du Referer pour les requêtes suivantes
            self._session.headers.update({"Referer": self.BASE_URL + "/"})
        except Exception as exc:
            logger.warning(f"[Hmizate] Impossible d'initialiser la session : {exc}")

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug="hmizate")
        async with self:
            # 1. Init session (cookies + Referer)
            await self._init_session()

            # 2. Tentative API JSON interne
            api_products = await self._try_api(run_log)
            if api_products:
                result.products.extend(api_products)
                logger.info(f"[Hmizate] API JSON → {len(api_products)} produits")
            else:
                # 3. Fallback : scraping HTML par catégorie
                for path in self.CATEGORY_PATHS:
                    url = self.BASE_URL + path
                    page = 1
                    while True:
                        sep = "&" if "?" in url else "?"
                        paginated = f"{url}{sep}page={page}"
                        self._session.headers.update({"Referer": url})
                        logger.info(f"[Hmizate] Scrape : {paginated}")
                        html = await self.fetch(paginated, run_log)
                        if not html:
                            break
                        products, has_next = self._parse_page(html, paginated)
                        result.products.extend(products)
                        result.pages_scraped += 1
                        if not has_next or page > 50:
                            break
                        page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    async def _try_api(self, run_log: list[str] | None) -> list[ScrapedProduct]:
        """Tente de récupérer les produits via une API JSON interne."""
        import json
        products: list[ScrapedProduct] = []

        for endpoint in self.API_ENDPOINTS:
            url = self.BASE_URL + endpoint
            html = await self.fetch(url, run_log)
            if not html:
                continue
            try:
                data = json.loads(html)
                parsed = self._parse_api(data, url)
                if parsed:
                    products.extend(parsed)
                    break    # un seul endpoint suffit
            except (json.JSONDecodeError, Exception):
                continue

        return products

    def _parse_api(self, data, source_url: str) -> list[ScrapedProduct]:
        """Parse une réponse JSON (plusieurs formats possibles)."""
        products = []

        # Normalise en liste
        if isinstance(data, dict):
            items = (
                data.get("deals") or data.get("products") or
                data.get("offers") or data.get("data") or
                data.get("results") or []
            )
        elif isinstance(data, list):
            items = data
        else:
            return []

        for item in items:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("name") or item.get("title") or
                item.get("nom") or item.get("product_name")
            )
            price_raw = (
                item.get("price") or item.get("promo_price") or
                item.get("deal_price") or item.get("prix") or
                item.get("prix_promo")
            )
            if not name or price_raw is None:
                continue
            try:
                price = float(str(price_raw).replace(",", "."))
            except ValueError:
                continue

            img_url = (
                item.get("image") or item.get("image_url") or
                item.get("thumbnail") or item.get("photo")
            )
            if img_url and img_url.startswith("/"):
                img_url = self.BASE_URL + img_url

            products.append(ScrapedProduct(
                name=name,
                price=price,
                category=(
                    item.get("category") or item.get("categorie") or
                    item.get("category_name")
                ),
                image_url=img_url,
                brand=item.get("brand") or item.get("store") or item.get("enseigne"),
                source_url=source_url,
            ))

        return products

    def _parse_page(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        """
        Parse une page HTML de catégorie.
        Couvre plusieurs structures possibles (PHP custom, PrestaShop, Laravel, etc.)
        """
        soup = self._soup(html)
        products = []

        # Sélecteurs larges : s'adapte à différentes structures HTML
        card_selectors = (
            ".deal-card, .deal-item, .bon-plan, .offer-item, "
            ".product-card, .product-item, .product-miniature, "
            ".js-product, article.item, .promo-card, .catalog-item, "
            "[class*='deal-'], [class*='product-card'], [class*='offer-']"
        )

        for item in soup.select(card_selectors):
            # Nom du produit
            name_el = item.select_one(
                ".deal-title, .product-title, .product-name, "
                ".offer-title, .item-title, .titre, "
                "h2, h3, h4, .name, .title, [class*='title'], [class*='name']"
            )
            # Prix promotionnel
            price_el = item.select_one(
                ".deal-price, .promo-price, .new-price, .sale-price, "
                ".product-price, .price, .prix, .prix-promo, "
                "[class*='price'], [class*='prix']"
            )
            # Image
            img_el = item.select_one("img")
            # Catégorie (depuis le fil d'ariane ou titre de page)
            cat_el = soup.select_one(
                "h1.page-title, h1.category-title, "
                ".breadcrumb li:last-child, .breadcrumbs li:last-child, "
                ".category-name, [class*='category-title']"
            )

            if not name_el or not price_el:
                continue

            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = (
                    img_el.get("data-src") or img_el.get("data-lazy-src") or
                    img_el.get("data-original") or img_el.get("src")
                )
                if img_url and img_url.startswith("/"):
                    img_url = self.BASE_URL + img_url
                # Ignore les placeholders
                if img_url and ("placeholder" in img_url or "data:image" in img_url):
                    img_url = None

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        # Pagination (nombreux formats)
        has_next = bool(soup.select_one(
            "a[rel=next], .next a, a.next, "
            "#pagination_next a, .pagination li.next:not(.disabled) a, "
            "[class*='pagination'] [class*='next']:not([class*='disabled'])"
        ))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 9. Scraper Générique (configurable via admin)
# ──────────────────────────────────────────────────────────────────────────────

class GenericScraper(EthicalScraperBase):
    """
    Scraper entièrement configurable via des sélecteurs CSS stockés en BDD.

    Exemple de config (ScraperConfig.selectors) :
    {
      "product":    ".product-item",
      "name":       ".product-name",
      "price":      ".price",
      "image":      "img.product-img",
      "category":   ".breadcrumb li:last-child",
      "next_page":  "a.next"
    }
    """

    def __init__(self, base_url: str, catalog_urls: list[str],
                 selectors: dict, rate_limit: float = 2.0,
                 slug: str = "generic"):
        super().__init__(rate_limit=rate_limit)
        self._base_url = base_url.rstrip("/")
        self._catalog_urls = catalog_urls
        self._sel = selectors
        self._slug = slug

    async def scrape(self, run_log: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult(config_slug=self._slug)
        async with self:
            for url in self._catalog_urls:
                full_url = url if url.startswith("http") else self._base_url + url
                page = 1
                while True:
                    sep = "&" if "?" in full_url else "?"
                    paginated = f"{full_url}{sep}page={page}"
                    html = await self.fetch(paginated, run_log)
                    if not html:
                        break
                    products, has_next = self._parse(html, paginated)
                    result.products.extend(products)
                    result.pages_scraped += 1
                    if not has_next or page > 100:
                        break
                    page += 1

        result.finished_at = datetime.now(timezone.utc)
        return result

    def _parse(self, html: str, source_url: str) -> tuple[list[ScrapedProduct], bool]:
        soup = self._soup(html)
        products = []
        sel = self._sel

        for item in soup.select(sel.get("product", ".product")):
            name_el  = item.select_one(sel.get("name", ".name"))
            price_el = item.select_one(sel.get("price", ".price"))
            img_el   = item.select_one(sel.get("image", "img"))
            cat_el   = soup.select_one(sel.get("category", ""))

            if not name_el or not price_el:
                continue
            price = self._price(price_el.get_text())
            if price is None:
                continue

            img_url = None
            if img_el:
                img_url = img_el.get("data-src") or img_el.get("src")
                if img_url and img_url.startswith("/"):
                    img_url = self._base_url + img_url

            products.append(ScrapedProduct(
                name=name_el.get_text(strip=True),
                price=price,
                category=cat_el.get_text(strip=True) if cat_el else None,
                image_url=img_url,
                source_url=source_url,
            ))

        has_next = bool(soup.select_one(sel.get("next_page", "a[rel=next]")))
        return products, has_next


# ──────────────────────────────────────────────────────────────────────────────
# 6. Déduplication
# ──────────────────────────────────────────────────────────────────────────────

class Deduplicator:
    """
    Déduplique les produits scrapés par :
    1. Fingerprint MD5 exact (nom normalisé + prix)
    2. Fuzzy matching sur le nom (SequenceMatcher ≥ 0.85)
    """
    FUZZY_THRESHOLD = 0.85

    def __init__(self):
        self._seen_fingerprints: set[str] = set()
        self._seen_names: list[str] = []

    def deduplicate(self, products: list[ScrapedProduct]) -> tuple[list[ScrapedProduct], int]:
        """Retourne (liste_unique, nb_doublons)."""
        unique: list[ScrapedProduct] = []
        duplicates = 0

        for product in products:
            if self._is_duplicate(product):
                duplicates += 1
                continue
            unique.append(product)
            self._seen_fingerprints.add(product.fingerprint)
            self._seen_names.append(product.name.lower().strip())

        return unique, duplicates

    def _is_duplicate(self, product: ScrapedProduct) -> bool:
        # Vérification exacte par fingerprint
        if product.fingerprint in self._seen_fingerprints:
            return True
        # Vérification fuzzy sur le nom
        name = product.name.lower().strip()
        for seen in self._seen_names:
            if SequenceMatcher(None, name, seen).ratio() >= self.FUZZY_THRESHOLD:
                return True
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 7. Orchestrateur
# ──────────────────────────────────────────────────────────────────────────────

SCRAPER_REGISTRY: dict[str, type[EthicalScraperBase]] = {
    "marjane":   MarjaneScraper,
    "carrefour": CarrefourScraper,
    "labelvie":  LabelVieScraper,
    "bim":       BimScraper,
    "kazyon":    KazyonScraper,
    "sopreco":   SoprecoScraper,
    "hmizate":   HmizateScraper,
}


class ScraperOrchestrator:
    """
    Orchestre l'exécution des scrapers, la déduplication,
    l'upload des images et la persistance en BDD.

    Usage :
        orchestrator = ScraperOrchestrator(db, storage)
        await orchestrator.run("marjane", triggered_by="admin")
    """

    def __init__(self, db=None, storage=None):
        self._db = db          # AsyncSession (optionnel pour les tests)
        self._storage = storage  # R2StorageService (optionnel)

    async def run(
        self,
        slug: str,
        triggered_by: str = "scheduler",
        config: dict | None = None,
    ) -> ScrapeResult:
        """
        Lance un scraper par son slug.
        `config` permet de passer une config générique (selectors, urls, etc.).
        """
        run_log: list[str] = []
        scraper = self._build_scraper(slug, config)

        if scraper is None:
            raise ValueError(f"Scraper inconnu : '{slug}'")

        scraper.on_captcha(self._on_captcha)

        logger.info(f"[Orchestrator] Démarrage scraper '{slug}' (déclenché par {triggered_by})")

        # ── Enregistrement du run en BDD ──────────────────────────────────────
        run = await self._create_run(slug, triggered_by)

        try:
            result = await scraper.scrape(run_log=run_log)

            # Déduplication
            deduplicator = Deduplicator()
            unique_products, n_duplicates = deduplicator.deduplicate(result.products)

            # Upload des images
            if self._storage:
                for product in unique_products:
                    if product.image_url:
                        local_url = await self._upload_image(product)
                        product.image_local_url = local_url

            # Persistance des produits
            n_new, n_updated = await self._save_products(unique_products, slug)

            # Mise à jour du run
            await self._update_run(run, result, n_new, n_updated, n_duplicates, run_log)

        except Exception as exc:
            logger.error(f"[Orchestrator] Erreur fatale pour '{slug}': {exc}", exc_info=True)
            await self._fail_run(run, str(exc))
            raise

        return result

    def _build_scraper(self, slug: str, config: dict | None) -> EthicalScraperBase | None:
        if slug in SCRAPER_REGISTRY:
            klass = SCRAPER_REGISTRY[slug]
            rate = (config or {}).get("rate_limit_seconds", 2.0)
            return klass(rate_limit=rate)

        if config:
            return GenericScraper(
                base_url=config["base_url"],
                catalog_urls=config.get("catalog_urls", []),
                selectors=config.get("selectors", {}),
                rate_limit=config.get("rate_limit_seconds", 2.0),
                slug=slug,
            )
        return None

    async def _on_captcha(self, url: str) -> None:
        logger.error(f"[CAPTCHA] Alerte admin — URL bloquée : {url}")
        # TODO: Envoyer email/Slack à l'admin

    async def _upload_image(self, product: ScrapedProduct) -> str | None:
        try:
            return await self._storage.upload_from_url(
                product.image_url,
                key=f"products/{product.fingerprint}.jpg",
            )
        except Exception as exc:
            logger.warning(f"Échec upload image pour '{product.name}': {exc}")
            return None

    # ── BDD helpers (no-op si db=None) ───────────────────────────────────────

    async def _create_run(self, slug: str, triggered_by: str):
        """Stub — implémenté dans le router admin avec la vraie session DB."""
        return {"id": None, "slug": slug, "triggered_by": triggered_by}

    async def _update_run(self, run, result, n_new, n_updated, n_dup, logs):
        pass  # Implémenté dans le router admin

    async def _fail_run(self, run, error):
        pass  # Implémenté dans le router admin

    async def _save_products(self, products: list[ScrapedProduct], slug: str) -> tuple[int, int]:
        """Stub — en production : upsert dans la table products + prices."""
        return len(products), 0
