"""Try Marjane APIM with correct Azure APIM header"""
import asyncio, httpx, json

API_BASE = "https://api-ayaline.marjane.ma"
API_KEY = "70593208-3197-4f72-8222-630026f72d0b-marjane-apim-prod"

async def test():
    # Try Azure APIM subscription key header
    headers_apim = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Ocp-Apim-Subscription-Key': API_KEY,  # Azure APIM standard header
        'Origin': 'https://www.marjane.ma',
        'Referer': 'https://www.marjane.ma/',
    }

    async with httpx.AsyncClient(timeout=20, headers=headers_apim, follow_redirects=True) as client:
        # Try endpoints that returned 401 (need auth) with proper Azure APIM header
        test_urls = [
            f"{API_BASE}/products?page=1&limit=20",
            f"{API_BASE}/products?categoryId=101",
            f"{API_BASE}/v1/products",
            # Maybe the API is nested
            f"{API_BASE}/marjane/products",
            f"{API_BASE}/marjane/v1/products",
            # Try with different area paths
            f"{API_BASE}/product",
            f"{API_BASE}/product?page=1&limit=20",
            f"{API_BASE}/items",
            f"{API_BASE}/item",
        ]

        for url in test_urls:
            try:
                r = await client.get(url, timeout=8)
                print(f"{r.status_code}: {url}")
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    print(f"  SUCCESS! {r.text[:500]}")
                elif r.status_code not in (404,):
                    if 'json' in r.headers.get('content-type', ''):
                        print(f"  {r.json()}")
                    print(f"  headers: {dict(r.headers)}")
            except Exception as e:
                print(f"  ERR: {e}")

asyncio.run(test())
