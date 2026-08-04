"""Test catalog API without empty Bearer and search for context"""
import asyncio, httpx, re

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'x-api-key': API_KEY,
        'Origin': 'https://www.marjane.ma',
        'Referer': 'https://www.marjane.ma/',
    }

    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Test catalog endpoints
        test_urls = [
            f"{API_BASE}/catalog",
            f"{API_BASE}/catalog?page=1&limit=20",
            f"{API_BASE}/catalog?categoryId=101",
            f"{API_BASE}/product-categories",
            f"{API_BASE}/coral/catalog",
            f"{API_BASE}/coral/product-categories",
        ]
        for url in test_urls:
            try:
                r = await client.get(url, timeout=8)
                print(f"{r.status_code}: {url}")
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    print(f"  SUCCESS! CT: {ct}")
                    print(f"  Response: {r.text[:500]}")
                elif r.status_code != 404:
                    ct = r.headers.get('content-type', '')
                    if 'json' in ct:
                        print(f"  {r.json()}")
            except Exception as e:
                print(f"  ERR: {e}")

        # Search app chunk for catalog context
        headers_web = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        r_app = await client.get(
            'https://www.marjane.ma/_next/static/chunks/pages/_app-c9389c6b008d935e.js',
            headers=headers_web
        )
        text = r_app.text

        # Find context around "/catalog"
        for m in re.finditer(r'"/catalog"', text):
            pos = m.start()
            ctx = text[max(0, pos-300):pos+300]
            print(f"\n'/catalog' context:")
            print(ctx)
            break

asyncio.run(test())
