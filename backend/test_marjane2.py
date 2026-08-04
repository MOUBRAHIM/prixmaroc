import asyncio, httpx, json, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        url = 'https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l'
        r = await client.get(url)

        soup = BeautifulSoup(r.text, 'html.parser')
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        data = json.loads(next_data.string)

        # Explore ssrData
        ssr = data.get('props', {}).get('pageProps', {}).get('ssrData', {})
        print('ssrData keys:', list(ssr.keys()) if isinstance(ssr, dict) else type(ssr))
        print('Full ssrData:', json.dumps(ssr, indent=2, ensure_ascii=False)[:2000])

asyncio.run(test())
