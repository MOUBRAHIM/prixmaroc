"""Find Marjane API endpoints from JS bundles"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        # Get main page and find JS bundle URLs
        r = await client.get('https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l')
        soup = BeautifulSoup(r.text, 'html.parser')

        # Find API calls in JS source
        script_urls = [s.get('src') for s in soup.find_all('script', src=True)]
        print(f"Script URLs: {len(script_urls)}")

        # Look for the main page bundle which likely contains API URLs
        for src in script_urls:
            if src and ('pages' in src or 'main' in src):
                url = 'https://www.marjane.ma' + src if src.startswith('/') else src
                print(f"Checking: {url}")
                r2 = await client.get(url)
                # Search for API endpoints
                api_matches = re.findall(r'["\'/](?:api|v\d)[^"\']{5,100}', r2.text)
                for m in set(api_matches[:20]):
                    print(f"  API: {m}")
                break

        # Try common Marjane API patterns
        test_apis = [
            'https://www.marjane.ma/api/v1/products/2298',
            'https://www.marjane.ma/api/products/2298',
            'https://api.marjane.ma/products/2298',
            'https://www.marjane.ma/api/v1/categories/101/products',
            'https://www.marjane.ma/api/courses-en-ligne/products?category=101',
        ]
        for url in test_apis:
            try:
                r3 = await client.get(url, timeout=5)
                if r3.status_code == 200:
                    print(f"FOUND API: {url}")
                    print(r3.text[:300])
                else:
                    print(f"  {r3.status_code}: {url}")
            except Exception as e:
                print(f"  ERR: {url}: {e}")

asyncio.run(test())
