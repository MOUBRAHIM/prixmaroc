"""Find the actual product list API fetch in JS chunks"""
import asyncio, httpx, re

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        # Check the large shared chunks for product fetching
        shared_chunks = [
            '/_next/static/chunks/8189-73a826641223f2d4.js',
            '/_next/static/chunks/pages/_app-c9389c6b008d935e.js',
        ]

        for chunk_path in shared_chunks:
            url = 'https://www.marjane.ma' + chunk_path
            r = await client.get(url)
            if r.status_code == 200:
                text = r.text
                # Find ProductList or catalog fetch patterns
                patterns = [
                    r'getProducts[^(]{0,50}\(',
                    r'fetchProducts[^(]{0,50}\(',
                    r'product[sS]Service[^.]{0,30}\.',
                    r'useProducts[^(]{0,30}\(',
                    r'/v\d/products',
                    r'getProductList',
                    r'productList',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, text)
                    if matches:
                        unique_matches = set(m.strip() for m in matches)
                        print(f"\n{chunk_path[-40:]} - '{pattern}':")
                        for m in list(unique_matches)[:5]:
                            # Find context
                            pos = text.find(m)
                            if pos >= 0:
                                ctx = text[max(0, pos-100):pos+150]
                                print(f"  {ctx[:200]}")

        # Also look at the chunk 8189 which has maps
        r8 = await client.get('https://www.marjane.ma/_next/static/chunks/8189-73a826641223f2d4.js')
        if r8.status_code == 200:
            text = r8.text
            # Look for API service or fetch patterns
            api_service = re.findall(r'(?:wynd|coral)[^;]{20,200}', text, re.IGNORECASE)
            print("\nwynd/coral patterns in chunk 8189:")
            for p in set(api_service[:5]):
                print(f"  {p[:150]}")

asyncio.run(test())
