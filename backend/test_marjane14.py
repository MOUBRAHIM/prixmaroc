"""Check the 200 response from courses-en-ligne API and chunk 341 for apiUrl"""
import asyncio, httpx, re, json
from bs4 import BeautifulSoup

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        # Check the 200 URL
        r = await client.get('https://www.marjane.ma/courses-en-ligne/api/products?category=101')
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', '')}")
        print(f"Content length: {len(r.text)}")
        try:
            data = r.json()
            print(f"JSON response: {json.dumps(data, ensure_ascii=False)[:1000]}")
        except:
            print(f"HTML response (first 500): {r.text[:500]}")

        # Check chunk 341 for apiUrl
        r2 = await client.get('https://www.marjane.ma/_next/static/chunks/341-aeb94bbcfa0e3b48.js')
        if r2.status_code == 200:
            text = r2.text
            # Find apiUrl value
            api_url_patterns = re.findall(r'apiUrl["\s:=]+["\`]([^"\'`\s]{10,150})["\`]', text, re.IGNORECASE)
            print(f"\nchunk 341 apiUrl patterns: {api_url_patterns}")
            # Find all https URLs
            all_https = re.findall(r'["\`](https://[^"\'`\s]{10,100})["\`]', text)
            print(f"All HTTPS URLs in chunk 341: {set(all_https)}")
            # Find environment configs
            env_config = re.findall(r'(?:NEXT_PUBLIC_|process\.env\.)[A-Z_]+', text)
            print(f"Env vars: {set(env_config)}")
            # Print first 2000 chars
            print(f"\nChunk 341 content (first 2000):\n{text[:2000]}")

asyncio.run(test())
