"""Extract API endpoints from Marjane JS bundles"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        all_api_urls = set()
        for src in script_urls[:10]:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=10)
                if r2.status_code == 200:
                    # Find URL patterns
                    matches = re.findall(r'["\'`]([^"\'`]*(?:product|catalog|categor|item|price)[^"\'`]{0,80})["\'`]', r2.text, re.IGNORECASE)
                    for m in matches:
                        if m.startswith('/') or m.startswith('http'):
                            all_api_urls.add(m[:100])
            except:
                pass

        print("API-like URLs found in JS:")
        for url in sorted(all_api_urls)[:40]:
            print(f"  {url}")

asyncio.run(test())
