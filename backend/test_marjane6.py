"""Check Marjane product page /product/ID"""
import asyncio, httpx, json, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/product/2298-bahia-eau-de-table-5l')
        soup = BeautifulSoup(r.text, 'html.parser')

        # Check __NEXT_DATA__ on this page
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            data = json.loads(next_data.string)
            page_props = data.get('props', {}).get('pageProps', {})
            print('pageProps keys:', list(page_props.keys()))
            text = json.dumps(page_props, ensure_ascii=False)
            # Find prices
            prices = re.findall(r'"price[^"]*":\s*(\d+\.?\d*)', text, re.IGNORECASE)
            names = re.findall(r'"(?:name|titre|title|nom)":\s*"([^"]+)"', text, re.IGNORECASE)
            print(f'Prices: {prices[:10]}')
            print(f'Names: {names[:5]}')
            # Print ssrData
            ssr = page_props.get('ssrData', {})
            if isinstance(ssr, dict):
                print('ssrData keys:', list(ssr.keys()))
            print('Full pageProps (500 chars):')
            print(text[:1000])
        else:
            print('No __NEXT_DATA__ on product page')

asyncio.run(test())
