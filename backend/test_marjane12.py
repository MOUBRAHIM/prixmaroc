"""Find the product list component (module 32589) to get the API endpoint"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=15)
                if r2.status_code == 200:
                    text = r2.text
                    # Look for module 32589 or any module with "products" fetch
                    if '32589' in text or ('product' in text.lower() and 'fetch' in text.lower()):
                        # Find fetch/get calls
                        api_calls = re.findall(r'(?:fetch|\.get|axios\.get)\(["\`]([^"\'`\)]{10,150})["\`]', text)
                        product_calls = [c for c in api_calls if 'product' in c.lower() or 'catalog' in c.lower() or 'item' in c.lower()]
                        if product_calls:
                            print(f"\n{src[-60:]}:")
                            for c in set(product_calls):
                                print(f"  {c}")

                        # Also search for URL templates
                        templates = re.findall(r'["\`](/[^"\'`\s]{5,80}(?:product|catalog|item)[^"\'`\s]{0,40})["\`]', text, re.IGNORECASE)
                        if templates:
                            print(f"Templates in {src[-40:]}:")
                            for t in set(templates):
                                print(f"  {t}")
            except Exception as e:
                pass

        # Also check the main webpack chunk which contains the API service
        for src in script_urls:
            if 'webpack' in src:
                url = 'https://www.marjane.ma' + src if src.startswith('/') else src
                r3 = await client.get(url)
                if r3.status_code == 200:
                    text = r3.text
                    print(f"\nwebpack chunk ({len(text)} chars)")
                    # Find any absolute URLs to backend
                    abs_urls = re.findall(r'["\`](https?://[^"\'`\s]{20,150})["\`]', text)
                    non_frontend = [u for u in abs_urls if 'marjane.ma' not in u and 'google' not in u and 'font' not in u]
                    if non_frontend:
                        print("Backend URLs in webpack:")
                        for u in set(non_frontend[:20]):
                            print(f"  {u}")

asyncio.run(test())
