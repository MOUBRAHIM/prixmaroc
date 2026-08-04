@echo off
REM start_all.bat — Lance backend Docker + tunnel Cloudflare + Expo en mode tunnel
REM Le telephone peut acceder a l'application depuis n'importe quel reseau

TITLE PrixMaroc — Lancement complet

echo ================================================
echo   PrixMaroc — Demarrage complet
echo ================================================
echo.

REM 1) Backend Docker
echo [1/3] Demarrage du backend...
cd /d "%~dp0.."
docker compose up -d
echo     OK

REM 2) Tunnel Cloudflare pour le backend (arriere-plan)
echo [2/3] Demarrage du tunnel Cloudflare (backend)...
start "Tunnel Backend" /min "%~dp0cloudflared.exe" tunnel --url http://localhost:8000 --logfile "%~dp0tunnel_backend.log"
timeout /t 6 /nobreak >nul
for /f "tokens=*" %%i in ('findstr /i "trycloudflare" "%~dp0tunnel_backend.log" 2^>nul') do (
    echo     URL Backend detectee
    echo     %%i
)
echo.
echo     ==> Copiez l URL trycloudflare ci-dessus dans l app (bouton Engrenage)
echo.

REM 3) Expo en mode tunnel (QR code accessible hors WiFi)
echo [3/3] Demarrage d Expo en mode tunnel...
echo     Scannez le QR code avec Expo Go depuis n importe quel reseau
echo.
cd /d "%~dp0..\mobile"
npm run tunnel

pause
