"""Service scraper — récupère les prix depuis les sites des enseignes."""
import asyncio
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings


@dataclass
class ScrapedPrice:
    product_name: str
    barcode: str | None
    price: float
    currency: str = "MAD"
    is_promo: bool = False
    promo_price: float | None = None


class ScraperService:
    """Scraper générique — adaptez les sélecteurs CSS selon chaque enseigne."""

    async def scrape_store(self, store_url: str, store_slug: str) -> list[ScrapedPrice]:
        """Scrape une page produit d'un magasin et retourne les prix trouvés."""
        html = await self._fetch(store_url)
        if not html:
            return []
        return self._parse(html, store_slug)

    async def _fetch(self, url: str) -> str | None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            print(f"[scraper] Erreur fetch {url}: {exc}")
            return None

    def _parse(self, html: str, store_slug: str) -> list[ScrapedPrice]:
        """
        Parseur générique — surcharger par enseigne si nécessaire.
        Sélecteurs attendus (schema.org Product):
          - [itemprop=name]
          - [itemprop=price]
          - [itemprop=gtin13]  (barcode)
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for product_el in soup.select("[itemtype*='schema.org/Product']"):
            name_el = product_el.select_one("[itemprop=name]")
            price_el = product_el.select_one("[itemprop=price]")
            barcode_el = product_el.select_one("[itemprop=gtin13]")

            if not name_el or not price_el:
                continue

            try:
                price_val = float(
                    price_el.get("content", price_el.text).replace(",", ".").strip()
                )
            except ValueError:
                continue

            results.append(
                ScrapedPrice(
                    product_name=name_el.text.strip(),
                    barcode=barcode_el.text.strip() if barcode_el else None,
                    price=price_val,
                )
            )

        return results
