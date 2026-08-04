"""Service IA — enrichissement produit, suggestions, détection de promos."""
import json
import httpx

from app.core.config import settings


class IAService:
    """
    Utilise un LLM (ex: Claude API) pour :
    - Enrichir les données produit depuis un texte OCR ou barcode
    - Suggérer des alternatives moins chères
    - Détecter les anomalies de prix
    """

    async def enrich_product(self, raw_name: str, barcode: str | None = None) -> dict:
        """Normalise un nom de produit brut et retourne des métadonnées structurées."""
        prompt = (
            f"Analyse ce nom de produit marocain et retourne un JSON avec les champs: "
            f"name (normalisé), brand, category, unit, unit_size.\n"
            f"Produit: '{raw_name}'"
            + (f"\nBarcode: {barcode}" if barcode else "")
        )
        return await self._call_llm(prompt)

    async def suggest_alternatives(self, product_name: str, budget: float) -> list[dict]:
        """Suggère des alternatives moins chères pour un produit donné."""
        prompt = (
            f"Suggère 3 alternatives moins chères au produit '{product_name}' "
            f"pour un budget de {budget} MAD au Maroc. "
            f"Retourne un JSON array avec: name, estimated_price, reason."
        )
        result = await self._call_llm(prompt)
        return result if isinstance(result, list) else []

    async def _call_llm(self, prompt: str) -> dict | list:
        """
        Appel au LLM configuré.
        TODO: Remplacer par l'intégration Claude/OpenAI réelle.
        """
        # Exemple avec l'API Anthropic:
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(
        #         "https://api.anthropic.com/v1/messages",
        #         headers={"x-api-key": settings.ANTHROPIC_API_KEY,
        #                  "anthropic-version": "2023-06-01"},
        #         json={"model": "claude-3-haiku-20240307", "max_tokens": 512,
        #               "messages": [{"role": "user", "content": prompt}]}
        #     )
        #     text = resp.json()["content"][0]["text"]
        #     return json.loads(text)
        return {"stub": "IA non configurée — ajoutez ANTHROPIC_API_KEY dans .env"}
