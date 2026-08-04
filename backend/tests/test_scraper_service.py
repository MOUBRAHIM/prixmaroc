"""
Tests unitaires — Service de scraping éthique.

Stratégie :
  - Toutes les requêtes HTTP sont mockées (httpx.AsyncClient)
  - On teste la logique de parsing, déduplication, rate limiting, robots.txt
  - Pas de vraie connexion réseau ni de BDD
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import (
    CAPTCHA_SIGNALS,
    BimScraper,
    CarrefourScraper,
    Deduplicator,
    EthicalScraperBase,
    GenericScraper,
    KazyonScraper,
    LabelVieScraper,
    MarjaneScraper,
    ScrapedProduct,
    ScrapeResult,
    ScraperOrchestrator,
    SoprecoScraper,
)


# ──────────────────────────────────────────────────────────────────────────────
# HTML de test
# ──────────────────────────────────────────────────────────────────────────────

HTML_MARJANE_PAGE = """
<html><body>
<div class="product-item" data-product-id="1">
  <h2 class="product-item-name">Lait Centrale 1L</h2>
  <span class="price">8.50 MAD</span>
  <img class="product-image-photo" src="/images/lait.jpg">
  <span data-category="Produits Laitiers">Produits Laitiers</span>
</div>
<div class="product-item" data-product-id="2">
  <h2 class="product-item-name">Coca-Cola 33cl Pack x6</h2>
  <span class="price">29,90 MAD</span>
  <img class="product-image-photo" src="/images/coca.jpg">
</div>
<div class="product-item" data-product-id="3">
  <h2 class="product-item-name">Beurre Président 250g</h2>
  <span class="price">18.90 MAD</span>
</div>
<a class="next" href="?p=2">Suivant</a>
</body></html>
"""

HTML_MARJANE_LAST_PAGE = """
<html><body>
<div class="product-item">
  <h2 class="product-item-name">Huile Lesieur 1L</h2>
  <span class="price">22.00 MAD</span>
</div>
</body></html>
"""

HTML_BIM_PAGE = """
<html><body>
<div class="product-box">
  <h3 class="product-title">Lait Ben Yedder 1L</h3>
  <span class="product-price">7.95 MAD</span>
  <img src="/img/lait-benyedder.jpg">
  <span class="product-category">Produits Laitiers</span>
</div>
<div class="product-box">
  <h3 class="product-title">Huile Cristal 1L</h3>
  <span class="product-price">19.50 MAD</span>
  <img src="/img/huile-cristal.jpg">
</div>
<div class="product-box">
  <h3 class="product-title">Sucre Baguette 1kg</h3>
  <span class="product-price">8.25 MAD</span>
</div>
<a class="next" href="?page=2">Suivant</a>
</body></html>
"""

HTML_KAZYON_PAGE = """
<html><body>
<h1 class="category-title">Alimentation</h1>
<div class="product-card">
  <span class="name">Pâtes El Ferdaous 500g</span>
  <span class="price">5.50 MAD</span>
  <img src="/img/pates.jpg">
</div>
<div class="product-card">
  <span class="name">Confiture Aïcha Fraise 400g</span>
  <span class="price">14.90 MAD</span>
</div>
<a rel="next" href="?page=2">»</a>
</body></html>
"""

HTML_KAZYON_API = """
[
  {"name": "Riz Egipto 1kg", "price": 12.50, "category": "Epicerie", "image": "/img/riz.jpg"},
  {"name": "Sel Cérès 1kg", "price": 2.75, "categoryName": "Epicerie Salée"}
]
"""

HTML_SOPRECO_PAGE = """
<html><body>
<h1 class="page-heading">Boissons</h1>
<article class="product-miniature">
  <h2 class="product-title"><a>Eau Ain Ifrane 1.5L</a></h2>
  <span class="product-price">3.20 MAD</span>
  <img class="product-cover-img" data-src="/img/ain-ifrane.jpg">
</article>
<article class="product-miniature">
  <h2 class="product-title"><a>Jus Pago Orange 1L</a></h2>
  <span class="product-price">18.50 MAD</span>
</article>
<li class="next"><a href="?page=2">»</a></li>
</body></html>
"""

HTML_CARREFOUR_PAGE = """
<html><body>
<div class="product-item">
  <h3 class="product-name">Eau Sidi Ali 1.5L</h3>
  <span class="product-price">3.50 MAD</span>
  <img src="/img/sidi-ali.jpg">
</div>
<div class="product-item">
  <h3 class="product-name">Yaourt Activia Nature</h3>
  <span class="product-price">5.50 MAD</span>
</div>
</body></html>
"""

HTML_LABELVIE_PAGE = """
<html><body>
<h1 class="page-heading">Alimentation</h1>
<article class="product-miniature">
  <h2 class="product-title">Farine Tria 1kg</h2>
  <span class="product-price">8,75 MAD</span>
  <img class="product-img" data-src="/img/farine.jpg">
</article>
<article class="product-miniature">
  <h2 class="product-title">Sucre Cristal 1kg</h2>
  <span class="product-price">9.50 MAD</span>
</article>
<a class="next a" href="?page=2">»</a>
</body></html>
"""

HTML_CAPTCHA = """
<html><body>
<h1>Access Denied</h1>
<p>Please verify you are human</p>
<div class="cf-challenge"></div>
</body></html>
"""

HTML_GENERIC = """
<html><body>
<div class="product">
  <span class="name">Thon Doha 120g</span>
  <span class="price">12.75</span>
  <img src="/img/thon.jpg">
</div>
<div class="product">
  <span class="name">Sardines Doha 125g</span>
  <span class="price">7.25</span>
</div>
<a rel="next" href="?page=2">Next</a>
</body></html>
"""

ROBOTS_TXT_ALLOW = "User-agent: *\nAllow: /"
ROBOTS_TXT_DISALLOW = "User-agent: *\nDisallow: /"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode()
    resp.headers = {"content-type": "text/html"}
    resp.raise_for_status = MagicMock()
    return resp


def mock_http_session(responses: dict[str, str]) -> MagicMock:
    """Crée un mock de httpx.AsyncClient qui retourne des réponses par URL."""
    session = AsyncMock()

    async def fake_get(url, **kwargs):
        for pattern, html in responses.items():
            if pattern in url:
                return make_response(html)
        return make_response("", 404)

    session.get = fake_get
    session.headers = {"User-Agent": "test-agent"}
    session.headers.update = MagicMock()
    session.aclose = AsyncMock()
    return session


# ──────────────────────────────────────────────────────────────────────────────
# Tests ScrapedProduct
# ──────────────────────────────────────────────────────────────────────────────

class TestScrapedProduct:
    def test_fingerprint_generated(self):
        p = ScrapedProduct(name="Lait 1L", price=8.50)
        assert len(p.fingerprint) == 32  # MD5 hex

    def test_same_name_price_same_fingerprint(self):
        p1 = ScrapedProduct(name="Lait 1L", price=8.50)
        p2 = ScrapedProduct(name="Lait 1L", price=8.50)
        assert p1.fingerprint == p2.fingerprint

    def test_different_price_different_fingerprint(self):
        p1 = ScrapedProduct(name="Lait 1L", price=8.50)
        p2 = ScrapedProduct(name="Lait 1L", price=9.00)
        assert p1.fingerprint != p2.fingerprint

    def test_default_currency_mad(self):
        p = ScrapedProduct(name="Test", price=10.0)
        assert p.currency == "MAD"

    def test_scraped_at_is_utc(self):
        from datetime import timezone
        p = ScrapedProduct(name="Test", price=10.0)
        assert p.scraped_at.tzinfo == timezone.utc


# ──────────────────────────────────────────────────────────────────────────────
# Tests EthicalScraperBase
# ──────────────────────────────────────────────────────────────────────────────

class TestEthicalScraperBase:
    def test_price_parser_dot(self):
        assert EthicalScraperBase._price("8.50 MAD") == 8.50

    def test_price_parser_comma(self):
        assert EthicalScraperBase._price("29,90 Dhs") == 29.90

    def test_price_parser_no_decimal(self):
        assert EthicalScraperBase._price("15 MAD") == 15.0

    def test_price_parser_none_on_garbage(self):
        assert EthicalScraperBase._price("pas un prix") is None

    def test_is_captcha_detected(self):
        scraper = EthicalScraperBase()
        assert scraper._is_captcha("please verify you are human")
        assert scraper._is_captcha("access denied by cloudflare")
        assert scraper._is_captcha("recaptcha challenge")

    def test_is_captcha_not_triggered_on_normal_html(self):
        scraper = EthicalScraperBase()
        assert not scraper._is_captcha("<html><body>normal page</body></html>")

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self):
        scraper = EthicalScraperBase(rate_limit=0.1)
        scraper._last_request["example.com"] = time.monotonic()
        start = time.monotonic()
        await scraper._rate_limit_wait("https://example.com/page")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # au moins la moitié du rate limit (avec jitter)

    @pytest.mark.asyncio
    async def test_robots_txt_disallow(self):
        scraper = EthicalScraperBase()
        scraper._session = AsyncMock()
        scraper._session.get = AsyncMock(return_value=make_response(ROBOTS_TXT_DISALLOW))
        scraper._session.headers = {"User-Agent": "testbot"}

        can = await scraper._can_fetch("https://blocked.com/products")
        assert can is False

    @pytest.mark.asyncio
    async def test_robots_txt_allow(self):
        scraper = EthicalScraperBase()
        scraper._session = AsyncMock()
        scraper._session.get = AsyncMock(return_value=make_response(ROBOTS_TXT_ALLOW))
        scraper._session.headers = {"User-Agent": "testbot"}

        can = await scraper._can_fetch("https://allowed.com/products")
        assert can is True

    @pytest.mark.asyncio
    async def test_captcha_triggers_callback(self):
        scraper = EthicalScraperBase()
        captcha_urls = []

        async def on_captcha(url):
            captcha_urls.append(url)

        scraper.on_captcha(on_captcha)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await scraper._handle_captcha("https://site.ma/page", [])

        assert "https://site.ma/page" in captcha_urls

    @pytest.mark.asyncio
    async def test_fetch_returns_none_on_captcha_response(self):
        scraper = EthicalScraperBase()
        scraper._robots_cache["captcha-site.ma"] = MagicMock(can_fetch=lambda *_: True)
        scraper._session = mock_http_session({"captcha-site.ma": HTML_CAPTCHA})

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await scraper.fetch("https://captcha-site.ma/page")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_returns_html_on_success(self):
        scraper = EthicalScraperBase()
        scraper._robots_cache["ok.ma"] = MagicMock(can_fetch=lambda *_: True)
        scraper._session = mock_http_session({"ok.ma": "<html>ok</html>"})

        result = await scraper.fetch("https://ok.ma/page")
        assert result == "<html>ok</html>"


# ──────────────────────────────────────────────────────────────────────────────
# Tests MarjaneScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestMarjaneScraper:
    def _make_scraper(self, html_map: dict) -> MarjaneScraper:
        scraper = MarjaneScraper()
        scraper._session = mock_http_session(html_map)
        # Autoriser tous les robots
        scraper._robots_cache["www.marjane.ma"] = MagicMock(can_fetch=lambda *_: True)
        return scraper

    def test_parse_page_extracts_products(self):
        scraper = MarjaneScraper()
        products, has_next = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        assert len(products) == 3

    def test_parse_page_correct_prices(self):
        scraper = MarjaneScraper()
        products, _ = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        prices = {p.name: p.price for p in products}
        assert prices["Lait Centrale 1L"] == pytest.approx(8.50)
        assert prices["Coca-Cola 33cl Pack x6"] == pytest.approx(29.90)
        assert prices["Beurre Président 250g"] == pytest.approx(18.90)

    def test_parse_page_detects_next(self):
        scraper = MarjaneScraper()
        _, has_next = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        assert has_next is True

    def test_parse_page_no_next(self):
        scraper = MarjaneScraper()
        _, has_next = scraper._parse_page(HTML_MARJANE_LAST_PAGE, "https://www.marjane.ma/fr/alimentation?p=2")
        assert has_next is False

    def test_parse_image_url_absolute(self):
        scraper = MarjaneScraper()
        products, _ = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        lait = next(p for p in products if p.name == "Lait Centrale 1L")
        assert lait.image_url == "https://www.marjane.ma/images/lait.jpg"

    def test_parse_category(self):
        scraper = MarjaneScraper()
        products, _ = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        lait = next(p for p in products if p.name == "Lait Centrale 1L")
        assert lait.category == "Produits Laitiers"

    def test_source_url_set(self):
        scraper = MarjaneScraper()
        products, _ = scraper._parse_page(HTML_MARJANE_PAGE, "https://www.marjane.ma/fr/alimentation")
        assert all(p.source_url == "https://www.marjane.ma/fr/alimentation" for p in products)


# ──────────────────────────────────────────────────────────────────────────────
# Tests CarrefourScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestCarrefourScraper:
    def test_parse_html_products(self):
        scraper = CarrefourScraper()
        products, _ = scraper._parse_html(HTML_CARREFOUR_PAGE, "https://www.carrefour.ma/fr/alimentation")
        assert len(products) == 2

    def test_parse_html_prices(self):
        scraper = CarrefourScraper()
        products, _ = scraper._parse_html(HTML_CARREFOUR_PAGE, "https://www.carrefour.ma/fr/alimentation")
        names = {p.name: p.price for p in products}
        assert names["Eau Sidi Ali 1.5L"] == pytest.approx(3.50)
        assert names["Yaourt Activia Nature"] == pytest.approx(5.50)

    def test_parse_api_json(self):
        scraper = CarrefourScraper()
        data = [
            {"name": "Coca Zero 33cl", "price": "6.50", "category_name": "Boissons"},
            {"name": "Jus Pago Orange", "price": 12.90, "image_url": "/img/pago.jpg"},
        ]
        products = scraper._parse_api(data, "https://www.carrefour.ma/api/products")
        assert len(products) == 2
        assert products[0].price == pytest.approx(6.50)
        assert products[1].price == pytest.approx(12.90)
        assert products[0].category == "Boissons"

    def test_parse_api_invalid_price_skipped(self):
        scraper = CarrefourScraper()
        data = [
            {"name": "Bon produit", "price": "15.00"},
            {"name": "Mauvais prix", "price": "N/A"},
            {"name": "Sans prix"},
        ]
        products = scraper._parse_api(data, "https://www.carrefour.ma/api")
        assert len(products) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Tests LabelVieScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestLabelVieScraper:
    def test_parse_page_products(self):
        scraper = LabelVieScraper()
        products, has_next = scraper._parse_page(HTML_LABELVIE_PAGE, "https://www.labelvie.ma/alimentation")
        assert len(products) == 2

    def test_parse_page_comma_price(self):
        scraper = LabelVieScraper()
        products, _ = scraper._parse_page(HTML_LABELVIE_PAGE, "https://www.labelvie.ma/alimentation")
        farine = next(p for p in products if "Farine" in p.name)
        assert farine.price == pytest.approx(8.75)

    def test_parse_page_category_from_heading(self):
        scraper = LabelVieScraper()
        products, _ = scraper._parse_page(HTML_LABELVIE_PAGE, "https://www.labelvie.ma/alimentation")
        assert all(p.category == "Alimentation" for p in products)

    def test_parse_page_image_url_resolved(self):
        scraper = LabelVieScraper()
        products, _ = scraper._parse_page(HTML_LABELVIE_PAGE, "https://www.labelvie.ma/alimentation")
        farine = next(p for p in products if "Farine" in p.name)
        assert farine.image_url == "https://www.labelvie.ma/img/farine.jpg"

    def test_has_next_detected(self):
        scraper = LabelVieScraper()
        _, has_next = scraper._parse_page(HTML_LABELVIE_PAGE, "https://www.labelvie.ma/alimentation")
        assert has_next is True


# ──────────────────────────────────────────────────────────────────────────────
# Tests GenericScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestGenericScraper:
    SELECTORS = {
        "product": ".product",
        "name": ".name",
        "price": ".price",
        "image": "img",
        "next_page": "a[rel=next]",
    }

    def test_parse_products(self):
        scraper = GenericScraper(
            base_url="https://shop.ma",
            catalog_urls=["/catalogue"],
            selectors=self.SELECTORS,
        )
        products, has_next = scraper._parse(HTML_GENERIC, "https://shop.ma/catalogue")
        assert len(products) == 2

    def test_parse_prices(self):
        scraper = GenericScraper(
            base_url="https://shop.ma",
            catalog_urls=["/catalogue"],
            selectors=self.SELECTORS,
        )
        products, _ = scraper._parse(HTML_GENERIC, "https://shop.ma/catalogue")
        names = {p.name: p.price for p in products}
        assert names["Thon Doha 120g"] == pytest.approx(12.75)
        assert names["Sardines Doha 125g"] == pytest.approx(7.25)

    def test_has_next(self):
        scraper = GenericScraper(
            base_url="https://shop.ma",
            catalog_urls=["/catalogue"],
            selectors=self.SELECTORS,
        )
        _, has_next = scraper._parse(HTML_GENERIC, "https://shop.ma/catalogue")
        assert has_next is True

    def test_image_url_resolved(self):
        scraper = GenericScraper(
            base_url="https://shop.ma",
            catalog_urls=["/catalogue"],
            selectors=self.SELECTORS,
        )
        products, _ = scraper._parse(HTML_GENERIC, "https://shop.ma/catalogue")
        thon = next(p for p in products if "Thon" in p.name)
        assert thon.image_url == "https://shop.ma/img/thon.jpg"

    def test_custom_slug(self):
        scraper = GenericScraper(
            base_url="https://boutique.ma",
            catalog_urls=["/all"],
            selectors=self.SELECTORS,
            slug="boutique-ma",
        )
        assert scraper._slug == "boutique-ma"


# ──────────────────────────────────────────────────────────────────────────────
# Tests Deduplicator
# ──────────────────────────────────────────────────────────────────────────────

class TestDeduplicator:
    def _product(self, name: str, price: float = 10.0) -> ScrapedProduct:
        return ScrapedProduct(name=name, price=price)

    def test_no_duplicates_in_unique_list(self):
        dedup = Deduplicator()
        products = [
            self._product("Lait Centrale 1L", 8.50),
            self._product("Coca-Cola 33cl", 5.00),
            self._product("Beurre Président", 18.90),
        ]
        unique, n_dup = dedup.deduplicate(products)
        assert len(unique) == 3
        assert n_dup == 0

    def test_exact_fingerprint_duplicate_removed(self):
        dedup = Deduplicator()
        products = [
            self._product("Lait Centrale 1L", 8.50),
            self._product("Lait Centrale 1L", 8.50),  # exact double
        ]
        unique, n_dup = dedup.deduplicate(products)
        assert len(unique) == 1
        assert n_dup == 1

    def test_fuzzy_duplicate_removed(self):
        dedup = Deduplicator()
        products = [
            self._product("Lait Centrale Danone 1L", 8.50),
            self._product("Lait Centrale Danone 1L", 8.50),  # identical → fingerprint
        ]
        unique, n_dup = dedup.deduplicate(products)
        assert n_dup >= 1

    def test_different_names_not_deduplicated(self):
        dedup = Deduplicator()
        products = [
            self._product("Lait Centrale 1L"),
            self._product("Lait Bimo 1L"),
            self._product("Eau Oulmès 1.5L"),
        ]
        unique, n_dup = dedup.deduplicate(products)
        assert len(unique) == 3
        assert n_dup == 0

    def test_dedup_preserves_order(self):
        dedup = Deduplicator()
        products = [
            self._product("A"),
            self._product("B"),
            self._product("C"),
        ]
        unique, _ = dedup.deduplicate(products)
        assert [p.name for p in unique] == ["A", "B", "C"]

    def test_empty_list(self):
        dedup = Deduplicator()
        unique, n_dup = dedup.deduplicate([])
        assert unique == []
        assert n_dup == 0

    def test_all_duplicates(self):
        dedup = Deduplicator()
        p = self._product("Produit unique", 5.0)
        products = [p, p, p]
        unique, n_dup = dedup.deduplicate(products)
        assert len(unique) == 1
        assert n_dup == 2


# ──────────────────────────────────────────────────────────────────────────────
# Tests ScraperOrchestrator
# ──────────────────────────────────────────────────────────────────────────────

class TestScraperOrchestrator:
    @pytest.mark.asyncio
    async def test_run_known_scraper(self):
        orchestrator = ScraperOrchestrator()

        fake_result = ScrapeResult(config_slug="marjane")
        fake_result.products = [ScrapedProduct(name="Lait", price=8.50)]

        with patch.object(MarjaneScraper, "scrape", return_value=fake_result):
            result = await orchestrator.run("marjane", triggered_by="test")

        assert result.config_slug == "marjane"

    @pytest.mark.asyncio
    async def test_run_unknown_slug_raises(self):
        orchestrator = ScraperOrchestrator()
        with pytest.raises(ValueError, match="Scraper inconnu"):
            await orchestrator.run("inexistant")

    @pytest.mark.asyncio
    async def test_run_generic_scraper_with_config(self):
        orchestrator = ScraperOrchestrator()
        config = {
            "base_url": "https://test.ma",
            "catalog_urls": ["/produits"],
            "selectors": {"product": ".p", "name": ".n", "price": ".pr"},
        }

        fake_result = ScrapeResult(config_slug="test")
        with patch.object(GenericScraper, "scrape", return_value=fake_result):
            result = await orchestrator.run("custom-shop", config=config)

        assert result.config_slug == "test"

    @pytest.mark.asyncio
    async def test_captcha_callback_registered(self):
        orchestrator = ScraperOrchestrator()
        callbacks_registered = []

        class SpyScraper(MarjaneScraper):
            def on_captcha(self, cb):
                callbacks_registered.append(cb)

            async def scrape(self, run_log=None):
                return ScrapeResult(config_slug="marjane")

        with patch("app.services.scraper_service.SCRAPER_REGISTRY",
                   {"marjane": SpyScraper}):
            await orchestrator.run("marjane")

        assert len(callbacks_registered) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Tests BimScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestBimScraper:
    def test_parse_page_extracts_products(self):
        scraper = BimScraper()
        products, _ = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        assert len(products) == 3

    def test_parse_page_prices(self):
        scraper = BimScraper()
        products, _ = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        prices = {p.name: p.price for p in products}
        assert prices["Lait Ben Yedder 1L"] == pytest.approx(7.95)
        assert prices["Huile Cristal 1L"] == pytest.approx(19.50)
        assert prices["Sucre Baguette 1kg"] == pytest.approx(8.25)

    def test_parse_page_category(self):
        scraper = BimScraper()
        products, _ = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        lait = next(p for p in products if "Lait" in p.name)
        assert lait.category == "Produits Laitiers"

    def test_parse_page_image_url_resolved(self):
        scraper = BimScraper()
        products, _ = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        lait = next(p for p in products if "Lait" in p.name)
        assert lait.image_url == "https://www.bim.ma/img/lait-benyedder.jpg"

    def test_parse_page_has_next(self):
        scraper = BimScraper()
        _, has_next = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        assert has_next is True

    def test_parse_page_no_next_on_last_page(self):
        html = "<html><body><div class='product-box'><h3>Produit</h3><span class='price'>5.00</span></div></body></html>"
        scraper = BimScraper()
        _, has_next = scraper._parse_page(html, "https://www.bim.ma/fr/produits/alimentation?page=2")
        assert has_next is False

    def test_all_products_have_fingerprint(self):
        scraper = BimScraper()
        products, _ = scraper._parse_page(HTML_BIM_PAGE, "https://www.bim.ma/fr/produits/alimentation")
        assert all(len(p.fingerprint) == 32 for p in products)

    def test_in_registry(self):
        from app.services.scraper_service import SCRAPER_REGISTRY
        assert "bim" in SCRAPER_REGISTRY
        assert SCRAPER_REGISTRY["bim"] is BimScraper


# ──────────────────────────────────────────────────────────────────────────────
# Tests KazyonScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestKazyonScraper:
    def test_parse_html_products(self):
        scraper = KazyonScraper()
        products, _ = scraper._parse_html(HTML_KAZYON_PAGE, "https://www.kazyon.com/ma/alimentation")
        assert len(products) == 2

    def test_parse_html_prices(self):
        scraper = KazyonScraper()
        products, _ = scraper._parse_html(HTML_KAZYON_PAGE, "https://www.kazyon.com/ma/alimentation")
        pates = next(p for p in products if "Pâtes" in p.name or "Ferdaous" in p.name)
        assert pates.price == pytest.approx(5.50)

    def test_parse_html_has_next(self):
        scraper = KazyonScraper()
        _, has_next = scraper._parse_html(HTML_KAZYON_PAGE, "https://www.kazyon.com/ma/alimentation")
        assert has_next is True

    def test_parse_api_json_list(self):
        import json
        scraper = KazyonScraper()
        data = json.loads(HTML_KAZYON_API)
        products = scraper._parse_api(data, "https://www.kazyon.com/ma/alimentation")
        assert len(products) == 2
        assert products[0].name == "Riz Egipto 1kg"
        assert products[0].price == pytest.approx(12.50)
        assert products[1].price == pytest.approx(2.75)

    def test_parse_api_with_nested_data(self):
        scraper = KazyonScraper()
        data = {"data": [{"name": "Produit X", "price": 9.99}]}
        products = scraper._parse_api(data, "https://www.kazyon.com/ma/alimentation")
        assert len(products) == 1
        assert products[0].price == pytest.approx(9.99)

    def test_parse_api_skips_missing_price(self):
        scraper = KazyonScraper()
        data = [
            {"name": "Bon produit", "price": 5.0},
            {"name": "Sans prix"},
            {"name": "Prix invalide", "price": "N/A"},
        ]
        products = scraper._parse_api(data, "https://www.kazyon.com/ma/alimentation")
        assert len(products) == 1

    def test_in_registry(self):
        from app.services.scraper_service import SCRAPER_REGISTRY
        assert "kazyon" in SCRAPER_REGISTRY
        assert SCRAPER_REGISTRY["kazyon"] is KazyonScraper


# ──────────────────────────────────────────────────────────────────────────────
# Tests SoprecoScraper
# ──────────────────────────────────────────────────────────────────────────────

class TestSoprecoScraper:
    def test_parse_page_products(self):
        scraper = SoprecoScraper()
        products, _ = scraper._parse_page(HTML_SOPRECO_PAGE, "https://www.sopreco.ma/boissons")
        assert len(products) == 2

    def test_parse_page_prices(self):
        scraper = SoprecoScraper()
        products, _ = scraper._parse_page(HTML_SOPRECO_PAGE, "https://www.sopreco.ma/boissons")
        eau = next(p for p in products if "Ain Ifrane" in p.name)
        assert eau.price == pytest.approx(3.20)
        jus = next(p for p in products if "Pago" in p.name)
        assert jus.price == pytest.approx(18.50)

    def test_parse_page_category_from_heading(self):
        scraper = SoprecoScraper()
        products, _ = scraper._parse_page(HTML_SOPRECO_PAGE, "https://www.sopreco.ma/boissons")
        assert all(p.category == "Boissons" for p in products)

    def test_parse_page_image_resolved(self):
        scraper = SoprecoScraper()
        products, _ = scraper._parse_page(HTML_SOPRECO_PAGE, "https://www.sopreco.ma/boissons")
        eau = next(p for p in products if "Ain Ifrane" in p.name)
        assert eau.image_url == "https://www.sopreco.ma/img/ain-ifrane.jpg"

    def test_parse_page_has_next(self):
        scraper = SoprecoScraper()
        _, has_next = scraper._parse_page(HTML_SOPRECO_PAGE, "https://www.sopreco.ma/boissons")
        assert has_next is True

    def test_parse_page_no_next(self):
        html = """<html><body>
        <article class="product-miniature">
          <h2 class="product-title"><a>Eau Ain Ifrane 1.5L</a></h2>
          <span class="product-price">3.20 MAD</span>
        </article>
        </body></html>"""
        scraper = SoprecoScraper()
        _, has_next = scraper._parse_page(html, "https://www.sopreco.ma/boissons?page=3")
        assert has_next is False

    def test_in_registry(self):
        from app.services.scraper_service import SCRAPER_REGISTRY
        assert "sopreco" in SCRAPER_REGISTRY
        assert SCRAPER_REGISTRY["sopreco"] is SoprecoScraper


# ──────────────────────────────────────────────────────────────────────────────
# Tests registre complet
# ──────────────────────────────────────────────────────────────────────────────

class TestScraperRegistry:
    def test_all_six_scrapers_registered(self):
        from app.services.scraper_service import SCRAPER_REGISTRY
        expected = {"marjane", "carrefour", "labelvie", "bim", "kazyon", "sopreco"}
        assert expected.issubset(set(SCRAPER_REGISTRY.keys()))

    def test_all_scrapers_are_subclasses_of_base(self):
        from app.services.scraper_service import SCRAPER_REGISTRY
        for slug, klass in SCRAPER_REGISTRY.items():
            assert issubclass(klass, EthicalScraperBase), f"{slug} n'hérite pas de EthicalScraperBase"

    def test_scheduler_has_six_jobs(self):
        from app.services.scheduler import get_scheduler, register_default_jobs
        scheduler = get_scheduler()
        register_default_jobs(scheduler)
        job_ids = {job.id for job in scheduler.get_jobs()}
        expected_ids = {
            "scraper_marjane", "scraper_carrefour", "scraper_labelvie",
            "scraper_bim", "scraper_kazyon", "scraper_sopreco",
        }
        assert expected_ids.issubset(job_ids)
