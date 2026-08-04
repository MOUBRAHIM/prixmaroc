"""Try schema.org structured data on Marjane product pages"""
import asyncio, httpx, json, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        # Get some product URLs from sitemap
        r_sitemap = await client.get('https://www.marjane.ma/sitemap.xml')
        product_urls = re.findall(r'<loc>(https://www\.marjane\.ma/courses-en-ligne/[^<]+)</loc>', r_sitemap.text)
        # Filter to specific product pages (5 levels deep)
        specific_products = [u for u in product_urls if u.count('/') >= 6][:10]
        print(f"Product URLs to check: {len(specific_products)}")

        for url in specific_products[:5]:
            r = await client.get(url)
            soup = BeautifulSoup(r.text, 'html.parser')

            # Check for schema.org JSON-LD
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                try:
                    data = json.loads(script.string)
                    if 'Product' in str(data.get('@type', '')):
                        print(f"\nFOUND PRODUCT SCHEMA at {url}!")
                        print(json.dumps(data, ensure_ascii=False)[:500])
                except:
                    pass

            # Check for Open Graph / meta tags with product info
            og_price = soup.find('meta', {'property': 'product:price:amount'})
            og_title = soup.find('meta', {'property': 'og:title'})
            if og_price:
                print(f"\nOG Price at {url}: {og_price.get('content')}")
                if og_title:
                    print(f"  Title: {og_title.get('content')}")

            # Check in __NEXT_DATA__ for product-specific data
            nd = soup.find('script', {'id': '__NEXT_DATA__'})
            if nd:
                data = json.loads(nd.string)
                text = json.dumps(data)
                prices = re.findall(r'"(?:price|prix)[^"]*":\s*(\d+\.?\d*)', text, re.IGNORECASE)
                if prices:
                    print(f"\nPrices in __NEXT_DATA__ at {url}: {prices[:5]}")
                # Check runtimeConfig
                rc = data.get('runtimeConfig', {})
                if rc and 'apiUrl' in rc:
                    print(f"  API URL: {rc['apiUrl']}")
                    print(f"  API Key: {rc.get('marjaneApiKey', 'not found')}")

asyncio.run(test())
