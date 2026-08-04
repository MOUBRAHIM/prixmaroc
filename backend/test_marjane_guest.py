"""Try Marjane API with anonymous/guest session"""
import asyncio, httpx, json

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'x-api-key': API_KEY,
        'Origin': 'https://www.marjane.ma',
        'Referer': 'https://www.marjane.ma/',
        'x-marjane-api-key': API_KEY,
    }

    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try to get an anonymous token first
        guest_endpoints = [
            f"{API_BASE}/auth/guest",
            f"{API_BASE}/auth/anonymous",
            f"{API_BASE}/v1/auth/token",
            f"{API_BASE}/token",
        ]
        for url in guest_endpoints:
            try:
                r = await client.post(url, json={}, timeout=8)
                print(f"POST {r.status_code}: {url}")
                if r.status_code in (200, 201):
                    print(f"  FOUND! {r.text[:300]}")
                elif 'json' in r.headers.get('content-type', ''):
                    print(f"  {r.json()}")
            except Exception as e:
                print(f"  ERR: {e}")

        # Try with area-based paths (from the code: queryArea with area="appliances")
        area_urls = [
            f"{API_BASE}/v1/catalog/appliances/product",
            f"{API_BASE}/catalog/appliances/product",
            f"{API_BASE}/products/appliances",
            f"{API_BASE}/area/appliances/products",
        ]
        print("\n--- Area-based endpoints ---")
        for url in area_urls:
            r = await client.get(url, timeout=8)
            print(f"{r.status_code}: {url}")
            if r.status_code == 200:
                print(f"  FOUND! {r.text[:300]}")

        # The wynd SDK likely has a specific URL pattern
        # Based on: s.$p.catalog.product.queryArea({queries:{...t,page:e}, params:{area:"appliances"}})
        # This suggests the URL might be: /catalog/product/area/appliances or /catalog/{area}/product
        wynd_patterns = [
            f"{API_BASE}/catalog/product/appliances",
            f"{API_BASE}/catalog/product?area=appliances&page=1",
            f"{API_BASE}/v2/catalog/product?area=appliances",
        ]
        print("\n--- Wynd-style endpoints ---")
        for url in wynd_patterns:
            r = await client.get(url, timeout=8)
            print(f"{r.status_code}: {url}")
            if r.status_code == 200:
                print(f"  FOUND! {r.text[:300]}")
            elif 'json' in r.headers.get('content-type', ''):
                print(f"  {r.json()}")

asyncio.run(test())
