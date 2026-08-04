"""Deep scan - find Marjane product API from page-specific chunk"""
import asyncio, httpx, re, json
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:

        # Get product page
        r = await client.get('https://www.marjane.ma/product/2298-bahia-eau-de-table-5l')
        soup = BeautifulSoup(r.text, 'html.parser')

        # Get all script chunks
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]
        print(f"Total scripts: {len(script_urls)}")

        # Search in all chunks for product-related keywords
        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=10)
                if r2.status_code == 200:
                    text = r2.text
                    # Look for marjane API URL patterns
                    if 'product' in text.lower() and ('fetch' in text.lower() or 'axios' in text.lower() or 'http' in text.lower()):
                        # Extract URL patterns
                        urls_found = re.findall(r'["\`](https?://[^"\'`\s]{20,150})["\`]', text)
                        external = [u for u in urls_found if 'marjane' in u and 'product' in u.lower()]
                        if external:
                            print(f"\nIn {src[-50:]}:")
                            for eu in set(external):
                                print(f"  {eu}")

                        # Look for internal API paths
                        internal = re.findall(r'["\`](/[^"\'`\s]{10,80})["\`]', text)
                        prod_internal = [u for u in internal if 'product' in u.lower() and 'next' not in u.lower()]
                        if prod_internal:
                            print(f"\nIn {src[-50:]} (internal):")
                            for u in set(prod_internal):
                                print(f"  {u}")
            except Exception as e:
                print(f"ERR {src[-40:]}: {e}")

        # Also try the promotions page which likely shows products with prices
        print("\n--- Testing promotions page ---")
        r3 = await client.get('https://www.marjane.ma/promotions')
        soup3 = BeautifulSoup(r3.text, 'html.parser')
        nd3 = soup3.find('script', {'id': '__NEXT_DATA__'})
        if nd3:
            data3 = json.loads(nd3.string)
            text3 = json.dumps(data3)
            prices3 = re.findall(r'"price[^"]*":\s*(\d+\.?\d*)', text3, re.IGNORECASE)
            names3 = re.findall(r'"(?:name|titre)[^"]*":\s*"([^"]{3,50})"', text3, re.IGNORECASE)
            print(f"Promotions page - Prices: {prices3[:5]}, Names: {names3[:5]}")
            props3 = data3.get('props', {}).get('pageProps', {})
            print("pageProps keys:", list(props3.keys()))

asyncio.run(test())
