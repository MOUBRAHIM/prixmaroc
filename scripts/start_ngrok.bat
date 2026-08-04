@echo off
REM start_ngrok.bat — Lance ngrok avec domaine statique
REM Remplacez VOTRE-DOMAINE par votre vrai domaine ngrok

REM Vérifier que Docker est démarré
docker info >nul 2>&1
if errorlevel 1 (
    echo [!] Docker n'est pas démarré. Démarrage...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 15 /nobreak >nul
)

REM Démarrer le backend si pas déjà actif
cd /d "%~dp0.."
docker compose up -d >nul 2>&1
echo [✓] Backend démarré

REM Démarrer ngrok avec domaine statique
echo [→] Démarrage du tunnel ngrok...
ngrok http --domain=VOTRE-DOMAINE.ngrok-free.app 8000

pause
