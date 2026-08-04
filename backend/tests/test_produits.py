import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient) -> str:
    await client.post("/auth/register", json={
        "email": "prod@prixmaroc.ma",
        "username": "produser",
        "password": "motdepasse123",
    })
    resp = await client.post("/auth/login", data={
        "username": "prod@prixmaroc.ma",
        "password": "motdepasse123",
    })
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_and_get_product(client: AsyncClient):
    token = await get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/produits/", json={
        "name": "Lait Centrale 1L",
        "slug": "lait-centrale-1l",
        "barcode": "6111234567890",
        "brand": "Centrale Danone",
        "unit": "L",
        "unit_size": "1L",
    }, headers=headers)
    assert resp.status_code == 201
    product_id = resp.json()["id"]

    resp = await client.get(f"/produits/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["barcode"] == "6111234567890"


@pytest.mark.asyncio
async def test_search_products(client: AsyncClient):
    resp = await client.get("/produits/?q=Lait")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
