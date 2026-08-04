"""Check product listing page chunk for API calls"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        # Get category page
        r = await client.get('https://www.marjane.ma/courses-en-ligne/6-eaux-boissons/25-eaux-sirops/101-eaux-plates')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]
        print(f"Scripts on category page: {len(script_urls)}")

        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            if 'pages' not in src and 'framework' not in src and 'polyfill' not in src:
                try:
                    r2 = await client.get(url, timeout=10)
                    if r2.status_code == 200:
                        text = r2.text
                        # Look for fetch patterns
                        fetches = re.findall(r'fetch\(["`]([^"`\)]+)["`]', text)
                        axios_gets = re.findall(r'\.get\(["`]([^"`\)]+)["`]', text)
                        all_calls = fetches + axios_gets
                        api_calls = [c for c in all_calls if len(c) > 5 and ('product' in c.lower() or 'catalog' in c.lower() or '/api/' in c.lower())]
                        if api_calls:
                            print(f"\n{src[-60:]}:")
                            for c in set(api_calls):
                                print(f"  FETCH: {c}")
                except Exception as e:
                    pass

        # Special: check pages/courses chunk
        for src in script_urls:
            if 'courses' in src or 'category' in src or 'produit' in src:
                url = 'https://www.marjane.ma' + src if src.startswith('/') else src
                print(f"\nFound relevant chunk: {src}")
                r2 = await client.get(url, timeout=10)
                if r2.status_code == 200:
                    # Print full content (small chunks only)
                    if len(r2.text) < 50000:
                        print(r2.text[:3000])
                    else:
                        # Search for key patterns
                        text = r2.text
                        for pattern in [r'url["\s:=]+["\`]([^"\'`\s]{15,100})["\`]', r'endpoint["\s:=]+["\`]([^"\'`\s]{15,100})["\`]']:
                            matches = re.findall(pattern, text, re.IGNORECASE)
                            print(f"Pattern matches: {matches[:5]}")

asyncio.run(test())
