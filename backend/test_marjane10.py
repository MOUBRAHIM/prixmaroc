"""Analyze main app chunk to find Marjane backend API URL"""
import asyncio, httpx, re
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        for src in script_urls:
            if '_app' in src or 'main' in src or 'framework' in src:
                url = 'https://www.marjane.ma' + src if src.startswith('/') else src
                r2 = await client.get(url)
                if r2.status_code == 200:
                    text = r2.text
                    # Find any HTTPS URLs that are not Marjane frontend
                    external_urls = re.findall(r'["\`](https://[^"\'`\s]{10,100})["\`]', text)
                    # Filter for API-like URLs
                    api_urls = set()
                    for u in external_urls:
                        if any(k in u for k in ['api', 'back', 'data', 'service', 'admin', 'shop', 'store']):
                            if 'google' not in u and 'font' not in u and 'analytic' not in u:
                                api_urls.add(u)
                    if api_urls:
                        print(f"\nIn {src[-60:]}:")
                        for u in sorted(api_urls):
                            print(f"  {u}")

                    # Find all API URL-like patterns including backend hostnames
                    hostnames = re.findall(r'https?://([a-zA-Z0-9\-\.]+\.[a-z]{2,6})', text)
                    unique_hosts = set(hostnames) - {'www.marjane.ma', 'marjane.ma', 'fonts.googleapis.com', 'fonts.gstatic.com'}
                    if unique_hosts:
                        print(f"\nUnique external hosts in {src[-40:]}:")
                        for h in sorted(unique_hosts):
                            print(f"  {h}")

asyncio.run(test())
