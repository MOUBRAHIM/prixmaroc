"""Extract the Wynd API endpoints for product catalog"""
import asyncio, httpx, re

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/_next/static/chunks/pages/_app-c9389c6b008d935e.js')
        text = r.text

        # Find getProducts implementation
        pos = text.find('getProducts:()=>On')
        if pos >= 0:
            ctx = text[pos:pos+500]
            print(f"getProducts context: {ctx}")

        # Find the On function definition
        # Look for "On" function around the area it's defined as getProducts
        # First find all function definitions of form "On=function" or "On=(..."
        matches = re.findall(r'\bOn\s*=\s*(?:function|\(|async)', text)
        print(f"\nOn= patterns: {matches[:5]}")

        # Look for the implementation of getProducts
        get_products_pos = [m.start() for m in re.finditer(r'getProducts\b', text)]
        print(f"\ngetProducts occurrences: {len(get_products_pos)}")
        for pos in get_products_pos[:5]:
            ctx = text[max(0, pos-50):pos+300]
            print(f"\n  At pos {pos}: ...{ctx}...")

        # More targeted: find the catalog/stock endpoint
        catalog_stock = [m.start() for m in re.finditer(r'catalog\.stock', text)]
        for pos in catalog_stock[:3]:
            ctx = text[max(0, pos-200):pos+400]
            print(f"\ncatalog.stock context: {ctx}")

        # Try the Wynd API catalog endpoint
        headers_api = {
            **headers,
            'Accept': 'application/json',
            'x-api-key': API_KEY,
            'Origin': 'https://www.marjane.ma',
        }
        wynd_urls = [
            f"{API_BASE}/catalog/stock?productID=101",
            f"{API_BASE}/catalog/stock?categoryId=101&page=1&limit=20",
            f"{API_BASE}/v1/catalog/stock",
            f"{API_BASE}/v1/products",
            f"{API_BASE}/catalog/products",
        ]
        print("\n--- Testing Wynd catalog endpoints ---")
        for url in wynd_urls:
            r2 = await client.get(url, headers=headers_api, timeout=8)
            print(f"{r2.status_code}: {url}")
            if r2.status_code == 200:
                print(f"  FOUND! {r2.text[:500]}")
            elif r2.status_code != 404:
                ct = r2.headers.get('content-type', '')
                if 'json' in ct:
                    print(f"  {r2.json()}")

asyncio.run(test())
