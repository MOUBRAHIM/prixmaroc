@echo off
REM start_tunnel.bat — Lance le tunnel Cloudflare + met à jour l'URL dans l'app
REM Usage: double-cliquez ou lancez depuis le dossier scripts\

TITLE PrixMaroc — Tunnel Cloudflare

echo ================================================
echo   PrixMaroc — Tunnel Cloudflare Quick
echo ================================================
echo.

REM Vérifier que Docker est démarré
docker info >nul 2>&1
if errorlevel 1 (
    echo [!] Docker n'est pas démarré. Démarrage...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo [~] Attente 20 secondes...
    timeout /t 20 /nobreak >nul
)

REM Démarrer le backend si pas déjà actif
cd /d "%~dp0.."
echo [~] Démarrage du backend...
docker compose up -d >nul 2>&1
echo [OK] Backend démarré

REM Attendre que le backend soit prêt
echo [~] Attente du backend...
timeout /t 5 /nobreak >nul

REM Vérifier que cloudflared est disponible
if not exist "%~dp0cloudflared.exe" (
    echo [!] cloudflared.exe non trouvé. Téléchargement...
    curl -L -o "%~dp0cloudflared.exe" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    echo [OK] cloudflared téléchargé
)

echo.
echo [->] Démarrage du tunnel Cloudflare...
echo [i]  Copiez l'URL https://*.trycloudflare.com affichée ci-dessous
echo [i]  Mettez-la dans mobile/src/constants/index.ts (ligne API_BASE_URL ngrok)
echo.
echo ================================================

REM Lancer le tunnel
"%~dp0cloudflared.exe" tunnel --url http://localhost:8000

pause
