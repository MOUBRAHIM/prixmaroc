"""Service Maps — géocodage et recherche de magasins proches."""
import httpx
from app.core.config import settings


class MapsService:
    BASE_URL = "https://maps.googleapis.com/maps/api"

    async def geocode(self, address: str) -> dict | None:
        """Convertit une adresse en coordonnées GPS."""
        params = {"address": address, "key": settings.GOOGLE_MAPS_KEY, "region": "ma"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/geocode/json", params=params)
            data = resp.json()
        if data.get("status") != "OK":
            return None
        location = data["results"][0]["geometry"]["location"]
        return {"lat": location["lat"], "lng": location["lng"]}

    async def reverse_geocode(self, lat: float, lng: float) -> str | None:
        """Convertit des coordonnées GPS en adresse lisible."""
        params = {"latlng": f"{lat},{lng}", "key": settings.GOOGLE_MAPS_KEY}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/geocode/json", params=params)
            data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        return data["results"][0]["formatted_address"]

    async def find_nearby_stores(self, lat: float, lng: float, radius_m: int = 5000) -> list[dict]:
        """Cherche des supermarchés proches via Places API."""
        params = {
            "location": f"{lat},{lng}",
            "radius": radius_m,
            "type": "supermarket",
            "key": settings.GOOGLE_MAPS_KEY,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/place/nearbysearch/json", params=params)
            data = resp.json()

        if data.get("status") != "OK":
            return []

        return [
            {
                "name": place["name"],
                "address": place.get("vicinity"),
                "lat": place["geometry"]["location"]["lat"],
                "lng": place["geometry"]["location"]["lng"],
                "google_place_id": place["place_id"],
            }
            for place in data.get("results", [])
        ]
