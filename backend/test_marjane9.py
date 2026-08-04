"""Try Marjane product search API"""
import asyncio, httpx, json

async def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, */*',
        'Referer': 'https://www.marjane.ma/',
    }
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try the search API
        search_urls = [
            'https://www.marjane.ma/product/search/?q=huile&page=1',
            'https://www.marjane.ma/api/v1/products/search?q=huile',
            'https://www.marjane.ma/api/products/search?q=huile',
        ]
        for url in search_urls:
            r = await client.get(url)
            print(f"{r.status_code}: {url}")
            if r.status_code == 200:
                ct = r.headers.get('content-type', '')
                print(f"  Content-Type: {ct}")
                if 'json' in ct:
                    print(f"  JSON: {r.text[:500]}")
                else:
                    print(f"  HTML length: {len(r.text)}")
                    # Check for __NEXT_DATA__ product info
                    import re
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.text, 'html.parser')
                    nd = soup.find('script', {'id': '__NEXT_DATA__'})
                    if nd:
                        data = json.loads(nd.string)
                        props = data.get('props', {}).get('pageProps', {})
                        print(f"  pageProps keys: {list(props.keys())}")
                        text = json.dumps(props)
                        prices = re.findall(r'"price[^"]*":\s*(\d+\.?\d*)', text, re.IGNORECASE)
                        names = re.findall(r'"(?:name|titre)[^"]*":\s*"([^"]{3,60})"', text, re.IGNORECASE)
                        print(f"  Prices: {prices[:5]}")
                        print(f"  Names: {names[:5]}")

        # Try category endpoint
        cat_urls = [
            'https://www.marjane.ma/product?firstLevel=6&page=1',
            'https://www.marjane.ma/product?secondLevel=25&page=1',
        ]
        for url in cat_urls:
            r = await client.get(url)
            print(f"\n{r.status_code}: {url}")
            if r.status_code == 200:
                from bs4 import BeautifulSoup
                import re
                soup = BeautifulSoup(r.text, 'html.parser')
                nd = soup.find('script', {'id': '__NEXT_DATA__'})
                if nd:
                    data = json.loads(nd.string)
                    props = data.get('props', {}).get('pageProps', {})
                    print(f"  pageProps keys: {list(props.keys())}")
                    text = json.dumps(props)
                    prices = re.findall(r'"(?:price|prix)[^"]*":\s*(\d+\.?\d*)', text, re.IGNORECASE)
                    print(f"  Prices: {prices[:10]}")
                    # Look for product arrays
                    if 'products' in text.lower():
                        idx = text.lower().find('products')
                        print(f"  Products context: {text[idx:idx+200]}")

asyncio.run(test())
