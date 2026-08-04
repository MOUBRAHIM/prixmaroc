import asyncio, httpx, json, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Test a specific product page from sitemap
        url = 'https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l'
        r = await client.get(url)
        print(f'Status: {r.status_code}')

        # Try __NEXT_DATA__
        soup = BeautifulSoup(r.text, 'html.parser')
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            try:
                data = json.loads(next_data.string)
                print('__NEXT_DATA__ found, keys:', list(data.get('props', {}).keys()))
                text = json.dumps(data)
                prices = re.findall(r'"price[^"]*":\s*(\d+\.?\d*)', text, re.IGNORECASE)
                names = re.findall(r'"name":\s*"([^"]+)"', text)
                print(f'Prices in data: {prices[:10]}')
                print(f'Names in data: {names[:5]}')
                # Print full pageProps
                page_props = data.get('props', {}).get('pageProps', {})
                print('pageProps keys:', list(page_props.keys()))
            except Exception as e:
                print(f'JSON parse error: {e}')
        else:
            print('No __NEXT_DATA__ found')
            # Try searching for price in text
            prices = re.findall(r'(\d+[.,]\d+)\s*(?:DH|MAD|dh)', r.text, re.IGNORECASE)
            print(f'Price patterns found: {prices[:10]}')

        # Also try Marjane API
        api_url = 'https://www.marjane.ma/api/category/101'
        try:
            r2 = await client.get(api_url)
            print(f'\nAPI {api_url}: {r2.status_code}')
            if r2.status_code == 200:
                print(r2.text[:500])
        except Exception as e:
            print(f'API error: {e}')

asyncio.run(test())
