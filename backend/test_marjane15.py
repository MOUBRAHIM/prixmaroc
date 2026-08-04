"""Find where w.apiUrl is defined in the app config"""
import asyncio, httpx, re, json
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get('https://www.marjane.ma/')
        soup = BeautifulSoup(r.text, 'html.parser')
        script_urls = [s.get('src') for s in soup.find_all('script', src=True) if s.get('src')]

        # The config/runtime config chunk usually has the API URL
        for src in script_urls:
            url = 'https://www.marjane.ma' + src if src.startswith('/') else src
            try:
                r2 = await client.get(url, timeout=15)
                if r2.status_code == 200:
                    text = r2.text
                    # Find apiUrl definition
                    if 'apiUrl' in text:
                        # Find context around apiUrl
                        positions = [m.start() for m in re.finditer('apiUrl', text)]
                        for pos in positions[:5]:
                            context = text[max(0, pos-100):pos+200]
                            print(f"\n{src[-50:]}:")
                            print(f"  Context: ...{context}...")
            except Exception as e:
                pass

        # Also check if there's a runtime config in the HTML
        print("\n--- Inline scripts on homepage ---")
        inline_scripts = [s.string for s in soup.find_all('script') if s.string and 'apiUrl' in s.string]
        for s in inline_scripts[:3]:
            print(f"Inline: {s[:500]}")

        # Check for __NEXT_RUNTIME_CONFIG__ or similar
        all_inline = [s.string for s in soup.find_all('script') if s.string]
        for s in all_inline:
            if s and any(k in s for k in ['apiUrl', 'API_URL', 'baseUrl', 'NEXT_PUBLIC']):
                print(f"\nConfig script: {s[:300]}")

asyncio.run(test())
