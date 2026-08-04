"""Try public Marjane API endpoints that might not need auth"""
import asyncio, httpx, json

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    headers = {
        'User-Agent': 'Marjane/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile',
        'Accept': 'application/json',
        'x-api-key': API_KEY,
        'x-wynd-env': 'production',
    }

    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try endpoints from code: getStores, getVersion, getTags
        public_endpoints = [
            f"{API_BASE}/stores",
            f"{API_BASE}/stores?area=appliances",
            f"{API_BASE}/version",
            f"{API_BASE}/v1/version",
            f"{API_BASE}/tags",
            f"{API_BASE}/promotions",
            f"{API_BASE}/promotions?page=1&limit=20",
            f"{API_BASE}/top-promotions",
            f"{API_BASE}/top-sales",
            f"{API_BASE}/product-categories",
            f"{API_BASE}/product-categories?page=1",
            f"{API_BASE}/categories",
            f"{API_BASE}/v1/stores",
        ]

        for url in public_endpoints:
            try:
                r = await client.get(url, timeout=8)
                print(f"{r.status_code}: {url}")
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    if 'json' in ct:
                        data = r.json()
                        print(f"  SUCCESS! {json.dumps(data, ensure_ascii=False)[:500]}")
                    else:
                        print(f"  SUCCESS! CT={ct}, len={len(r.text)}")
                elif r.status_code not in (404, 403):
                    print(f"  Body: {r.text[:100]}")
            except Exception as e:
                print(f"  ERR: {e}")

asyncio.run(test())
