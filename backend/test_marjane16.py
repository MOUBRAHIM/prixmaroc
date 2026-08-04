"""Find Next.js publicRuntimeConfig with apiUrl"""
import asyncio, httpx, re, json
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/')

        # Search for publicRuntimeConfig in the full HTML
        text = r.text
        if 'publicRuntimeConfig' in text:
            pos = text.find('publicRuntimeConfig')
            print(f"publicRuntimeConfig found at pos {pos}:")
            print(text[max(0, pos-50):pos+500])
        else:
            print("publicRuntimeConfig NOT in page HTML")

        # Look for __NEXT_RUNTIME_CONFIG in the page
        soup = BeautifulSoup(r.text, 'html.parser')
        for script in soup.find_all('script'):
            s = script.string or ''
            if 'publicRuntimeConfig' in s or 'runtimeConfig' in s or 'NEXT_PUBLIC' in s:
                print(f"\nFound runtime config script: {s[:800]}")
                break

        # Try to access the Next.js runtime config endpoint
        config_urls = [
            'https://www.marjane.ma/_next/static/development/_devPagesManifest.json',
            'https://www.marjane.ma/_next/static/chunks/polyfills-42372ed130431b0a.js',
        ]

        # Try to get config from __NEXT_DATA__ query key
        next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data_script:
            data = json.loads(next_data_script.string)
            # Check for runtimeConfig
            if 'runtimeConfig' in data:
                print(f"\nruntimeConfig: {json.dumps(data['runtimeConfig'])[:500]}")
            print("All __NEXT_DATA__ top-level keys:", list(data.keys()))
            print("Full data:", json.dumps(data, indent=2, ensure_ascii=False)[:2000])

asyncio.run(test())
