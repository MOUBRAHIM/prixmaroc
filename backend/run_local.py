"""
Lance le backend PrixMaroc en LOCAL pour tester l'app mobile (Expo Go).

- Force la boucle d'événements Selector (obligatoire pour psycopg async sous Windows).
- Écoute sur 0.0.0.0:8000 pour être joignable depuis le téléphone sur le même WiFi.
- Utilise la config de backend/.env (DATABASE_URL = Neon).

Usage (PowerShell, dans le dossier backend) :
    python run_local.py
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    print("=== PrixMaroc backend LOCAL ===")
    print("API joignable sur : http://192.168.0.116:8000  (et http://localhost:8000)")
    print("Docs : http://192.168.0.116:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1, log_level="info")
