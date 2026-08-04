import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "test@prixmaroc.ma",
        "username": "testuser",
        "password": "motdepasse123",
        "city": "Casablanca",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@prixmaroc.ma"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@prixmaroc.ma", "username": "dup1", "password": "motdepasse123"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json={**payload, "username": "dup2"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "login@prixmaroc.ma",
        "username": "loginuser",
        "password": "motdepasse123",
    })
    resp = await client.post("/auth/login", data={
        "username": "login@prixmaroc.ma",
        "password": "motdepasse123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post("/auth/login", data={
        "username": "login@prixmaroc.ma",
        "password": "mauvais",
    })
    assert resp.status_code == 401
