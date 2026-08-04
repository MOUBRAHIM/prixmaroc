"""Try Marjane Next.js API routes"""
import asyncio, httpx, json

async def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'x-nextjs-data': '1',
    }
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Try Next.js data endpoints
        test_urls = [
            # Next.js SSR data endpoint
            'https://www.marjane.ma/_next/data/build-id/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l.json',
            # Try with actual build ID from the page
        ]

        # First get the build ID
        r = await client.get('https://www.marjane.ma/', headers={'User-Agent': headers['User-Agent']})
        import re
        build_id = re.search(r'"buildId":"([^"]+)"', r.text)
        if build_id:
            bid = build_id.group(1)
            print(f"Build ID: {bid}")
            # Try Next.js data route
            data_urls = [
                f'https://www.marjane.ma/_next/data/{bid}/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates/2298-bahia-eau-de-table-5l.json',
                f'https://www.marjane.ma/_next/data/{bid}/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates.json',
                f'https://www.marjane.ma/_next/data/{bid}/courses-en-ligne.json',
            ]
            for url in data_urls:
                try:
                    r2 = await client.get(url)
                    print(f"{r2.status_code}: {url[-80:]}")
                    if r2.status_code == 200:
                        data = r2.json()
                        print(f"  Keys: {list(data.get('pageProps', {}).keys())}")
                        text = json.dumps(data)
                        prices = re.findall(r'"(?:price|prix)[^"]*":\s*"?(\d+\.?\d*)"?', text, re.IGNORECASE)
                        names = re.findall(r'"(?:name|nom|title)[^"]*":\s*"([^"]{3,60})"', text, re.IGNORECASE)
                        print(f"  Prices: {prices[:5]}, Names: {names[:5]}")
                except Exception as e:
                    print(f"  ERR: {e}")
        else:
            print("Build ID not found")

        # Try /product API endpoint
        product_tests = [
            'https://www.marjane.ma/product?id=2298',
            'https://www.marjane.ma/product/2298-bahia-eau-de-table-5l',
            'https://www.marjane.ma/api/product?id=2298',
        ]
        for url in product_tests:
            try:
                r3 = await client.get(url)
                print(f"{r3.status_code}: {url}")
                if r3.status_code == 200 and 'json' in r3.headers.get('content-type', ''):
                    print(f"  JSON: {r3.text[:200]}")
            except Exception as e:
                print(f"  ERR {url}: {e}")

asyncio.run(test())
