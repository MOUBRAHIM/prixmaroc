"""Direct Marjane API scraping via api-ayaline.marjane.ma"""
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
    }

    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try common API endpoints
        test_urls = [
            f"{API_BASE}/products?page=1&limit=20",
            f"{API_BASE}/products?categoryId=101&page=1",
            f"{API_BASE}/v1/products?categoryId=101",
            f"{API_BASE}/v2/products?categoryId=101",
            f"{API_BASE}/catalog/products?categoryId=101",
            f"{API_BASE}/categories/101/products",
            f"{API_BASE}/items?category=101",
            f"{API_BASE}/search?q=huile&type=product",
            f"{API_BASE}/cms/v2/items/products?filter[is_active][_eq]=true&limit=10",
            f"{API_BASE}/cms/v2/items/category?limit=20",
        ]

        for url in test_urls:
            try:
                r = await client.get(url, timeout=10)
                print(f"{r.status_code}: {url}")
                if r.status_code == 200:
                    ct = r.headers.get('content-type', '')
                    print(f"  Content-Type: {ct}")
                    if 'json' in ct:
                        data = r.json()
                        print(f"  JSON keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        if isinstance(data, dict):
                            print(f"  Data: {json.dumps(data, ensure_ascii=False)[:500]}")
                        elif isinstance(data, list):
                            print(f"  List length: {len(data)}, first item: {json.dumps(data[0], ensure_ascii=False)[:300] if data else 'empty'}")
            except Exception as e:
                print(f"  ERR: {url}: {e}")

asyncio.run(test())
