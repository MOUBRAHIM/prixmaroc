"""Look at all chunks for any URL pattern with numbers - they're likely the actual API"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        # Focus on the big chunks (likely the app code)
        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=15)
                if r2.status_code == 200 and len(r2.text) > 10000:
                    text = r2.text
                    # Look for environment variables / config strings
                    env_patterns = re.findall(r'(?:NEXT_PUBLIC_|API_URL|BASE_URL|apiUrl|baseUrl|apiBase)[^,;}\n]{3,100}', text)
                    if env_patterns:
                        print(f"\n{src[-50:]}:")
                        for p in env_patterns[:5]:
                            print(f"  {p}")

                    # Look for hardcoded backend URLs
                    backend = re.findall(r'["\`]((?:https?://)?(?:[a-z0-9\-]+\.){2,4}[a-z]{2,6}/[^"\'`\s]{5,80})["\`]', text)
                    backend_filtered = [b for b in backend if any(k in b for k in ['product', 'catalog', 'items', 'prices', '/api/', '/v1/', '/v2/']) and 'marjane.ma' not in b]
                    if backend_filtered:
                        print(f"Backend API in {src[-40:]}:")
                        for b in set(backend_filtered[:10]):
                            print(f"  {b}")
            except Exception as e:
                pass

        # Try direct API probing with common Moroccan e-commerce patterns
        print("\n--- Probing direct API endpoints ---")
        test_urls = [
            'https://api.marjane.ma/v1/products?categoryId=101&page=1&limit=20',
            'https://backend.marjane.ma/api/products',
            'https://www.marjane.ma/api/v1/categories/101/products?page=1',
            'https://www.marjane.ma/api/v2/products?category=101',
            'https://www.marjane.ma/courses-en-ligne/api/products?category=101',
        ]
        for url in test_urls:
            try:
                r3 = await client.get(url, timeout=5)
                print(f"  {r3.status_code}: {url}")
            except Exception as e:
                print(f"  ERR: {url} ({type(e).__name__})")

asyncio.run(test())
