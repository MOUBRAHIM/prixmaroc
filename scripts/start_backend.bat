@echo off
chcp 65001 >nul
title PrixMaroc — Backend + Tunnel

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              PRIXMAROC — Démarrage Backend               ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM Aller dans le dossier projet
cd /d "C:\Users\HP 840 G7\Desktop\PrixMaroc"

echo [1/2] Démarrage Docker (backend + base de données)...
docker-compose up -d
echo.

echo [2/2] Démarrage du tunnel Cloudflare...
echo.

REM Vérifier si tunnel nommé existe
cloudflared tunnel list 2>nul | findstr "prixmaroc" >nul
if %ERRORLEVEL% == 0 (
    echo Tunnel permanent "prixmaroc" détecté.
    echo.

    REM Afficher l'URL stable
    echo ════════════════════════════════════════════════
    echo  URL DE L'API (à mettre dans l'app) :
    cloudflared tunnel info prixmaroc 2>&1 | findstr "cfargotunnel" | for /f "tokens=*" %%a in ('more') do echo  https://%%a
    echo ════════════════════════════════════════════════
    echo.

    REM Lancer le tunnel permanent dans une nouvelle fenêtre
    start "Cloudflare Tunnel" cloudflared tunnel run --url http://localhost:8000 prixmaroc
) else (
    echo Tunnel temporaire (URL change à chaque démarrage).
    echo Pour une URL PERMANENTE, lancez d'abord: scripts\1_setup_tunnel.bat
    echo.

    REM Démarrer un quick tunnel et afficher l'URL
    echo Démarrage tunnel temporaire...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8000 2>&1"
    timeout /t 5 >nul
    echo.
    echo [!] Regardez la fenêtre "Cloudflare Tunnel" pour voir l'URL
    echo [!] Cherchez la ligne: trycloudflare.com
    echo.
)

echo.
echo Backend accessible sur: http://localhost:8000
echo Docs API:               http://localhost:8000/docs
echo Admin panel:            http://localhost:5173
echo.
echo Appuyez sur une touche pour ouvrir les docs API dans le navigateur...
pause >nul
start http://localhost:8000/docs

echo.
echo [OK] PrixMaroc démarré. Gardez cette fenêtre ouverte.
pause
