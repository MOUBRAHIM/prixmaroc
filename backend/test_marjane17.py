"""Try Marjane coral API and find exact product endpoint"""
import asyncio, httpx, re, json
from bs4 import BeautifulSoup

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"
CORAL_URL = f"{API_BASE}/coral"

async def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'x-api-key': API_KEY,
        'Origin': 'https://www.marjane.ma',
        'Referer': 'https://www.marjane.ma/',
    }

    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try coral API (the product catalog)
        coral_urls = [
            f"{CORAL_URL}/categories",
            f"{CORAL_URL}/products?category=101",
            f"{CORAL_URL}/products?page=1&limit=20",
            f"{API_BASE}/coral/v1/products",
            f"{API_BASE}/coral/catalog/products?page=1",
        ]
        for url in coral_urls:
            try:
                r = await client.get(url, timeout=10)
                print(f"{r.status_code}: {url}")
                if r.status_code in (200, 401, 403):
                    ct = r.headers.get('content-type', '')
                    if 'json' in ct:
                        print(f"  JSON: {r.text[:300]}")
            except Exception as e:
                print(f"  ERR: {url}: {e}")

        # Look in app chunk for the exact URL patterns used
        r2 = await client.get('https://www.marjane.ma/_next/static/chunks/pages/_app-c9389c6b008d935e.js')
        text = r2.text

        # Find coral API usage
        coral_patterns = re.findall(r'coral[^,;}\n]{5,200}', text, re.IGNORECASE)
        print("\nCoral patterns in app:")
        for p in set(coral_patterns[:20]):
            print(f"  {p[:100]}")

        # Find wynd usage (also in the code: t.wynd.url=w.apiUrl)
        # wynd might be the product catalog
        wynd_patterns = re.findall(r'wynd[^,;}\n]{5,150}', text, re.IGNORECASE)
        print("\nWynd patterns:")
        for p in set(wynd_patterns[:10]):
            print(f"  {p[:100]}")

        # Find any URL construction with the base API
        url_constructs = re.findall(r'["\`]' + re.escape(API_BASE) + r'[^"\'`\s]{0,100}["\`]', text)
        print(f"\nDirect API URL constructs: {url_constructs}")

        # Extract all URL template strings
        template_urls = re.findall(r'`\$\{[^}]+\}[^`]{0,100}`', text)
        product_templates = [t for t in template_urls if 'product' in t.lower() or 'catalog' in t.lower() or 'item' in t.lower()]
        print("\nProduct URL templates:")
        for t in product_templates[:10]:
            print(f"  {t}")

asyncio.run(test())
