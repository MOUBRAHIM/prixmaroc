"""Find the catalog and product-categories endpoint"""
import asyncio, httpx, re

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    headers_api = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'x-api-key': API_KEY,
        'Authorization': 'Bearer ',  # Will be empty without token
        'Origin': 'https://www.marjane.ma',
        'Referer': 'https://www.marjane.ma/',
    }

    async with httpx.AsyncClient(timeout=20, headers=headers_api, follow_redirects=True) as client:
        # Based on templates: ${ne}/catalog, ${ne}/product-categories
        # ne is likely the apiUrl or apiUrl + "/coral"
        test_combinations = [
            (API_BASE, 'catalog'),
            (API_BASE, 'product-categories'),
            (f"{API_BASE}/coral", 'catalog'),
            (f"{API_BASE}/coral", 'product-categories'),
            (f"{API_BASE}/coral", 'catalog?page=1&limit=20'),
            (f"{API_BASE}/coral", 'catalog?categoryId=101'),
            (API_BASE, 'catalog?page=1&limit=20'),
            (API_BASE, 'catalog?categoryId=101'),
        ]
        for base, path in test_combinations:
            url = f"{base}/{path}"
            try:
                r = await client.get(url, timeout=8)
                print(f"{r.status_code}: {url}")
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    print(f"  SUCCESS! CT: {ct}")
                    print(f"  Response: {r.text[:500]}")
                elif r.status_code in (401, 403, 404):
                    if 'json' in r.headers.get('content-type', ''):
                        print(f"  {r.json()}")
            except Exception as e:
                print(f"  ERR: {e}")

        # Also look in the app chunk for ne and we variables
        r_app = await client.get(
            'https://www.marjane.ma/_next/static/chunks/pages/_app-c9389c6b008d935e.js',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        text = r_app.text
        # Find context around catalog template
        catalog_pos = [m.start() for m in re.finditer(r'/catalog', text)]
        for pos in catalog_pos[:5]:
            ctx = text[max(0, pos-200):pos+200]
            print(f"\nCatalog context: ...{ctx}...")

asyncio.run(test())
