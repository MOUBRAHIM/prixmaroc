"""Find Marjane internal API from JS chunks"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        all_patterns = set()
        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=10)
                if r2.status_code == 200:
                    text = r2.text
                    # Look for fetch/axios calls with paths
                    patterns = re.findall(r'fetch\(["\`]([^"\'`\)]{5,100})["\`]', text)
                    patterns += re.findall(r'axios\.[a-z]+\(["\`]([^"\'`\)]{5,100})["\`]', text)
                    patterns += re.findall(r'["\`](/(?:api|v\d|rest|graphql)[^"\'`\s]{5,100})["\`]', text)
                    patterns += re.findall(r'baseURL["\s:=]+["\`]([^"\'`\s]{10,100})["\`]', text)
                    for p in patterns:
                        if any(k in p for k in ['product', 'catalog', 'price', 'item', 'api', 'graphql']):
                            all_patterns.add(p)
            except Exception as e:
                pass

        print("Found API patterns:")
        for p in sorted(all_patterns):
            print(f"  {p}")

        # Try GraphQL
        graphql_url = 'https://www.marjane.ma/graphql'
        r3 = await client.post(graphql_url, json={"query": "{ __typename }"}, headers={**headers, 'Content-Type': 'application/json'})
        print(f"\nGraphQL: {r3.status_code}")

        # Try Magento REST API (many MA sites use Magento)
        magento_urls = [
            'https://www.marjane.ma/rest/V1/products?searchCriteria[pageSize]=5',
            'https://www.marjane.ma/rest/default/V1/products?searchCriteria[pageSize]=5',
        ]
        for url in magento_urls:
            r4 = await client.get(url)
            print(f"{r4.status_code}: {url}")
            if r4.status_code == 200:
                print(f"  {r4.text[:300]}")

asyncio.run(test())
