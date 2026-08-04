@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         PRIXMAROC — Configuration Tunnel Cloudflare      ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo Ce script crée un tunnel PERMANENT avec URL fixe.
echo Il suffit de le faire UNE SEULE FOIS.
echo.

REM Vérifier si déjà authentifié
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo [OK] Cloudflare déjà authentifié.
    goto :create_tunnel
)

echo ÉTAPE 1/3 — Connexion à Cloudflare
echo -------------------------------------------
echo Un navigateur va s'ouvrir. Connectez-vous à votre compte
echo Cloudflare (gratuit sur cloudflare.com) puis autorisez.
echo.
pause
cloudflared tunnel login
echo.

:create_tunnel
echo ÉTAPE 2/3 — Création du tunnel "prixmaroc"
echo -------------------------------------------
cloudflared tunnel create prixmaroc 2>&1
echo.

echo ÉTAPE 3/3 — Création du fichier de configuration
echo -------------------------------------------

REM Récupérer l'UUID du tunnel
for /f "tokens=*" %%i in ('cloudflared tunnel list 2^>^&1 ^| findstr "prixmaroc" ^| for /f "tokens=1" %%a in ("%%i") do echo %%a') do set TUNNEL_ID=%%i

REM Créer le dossier de config
if not exist "%USERPROFILE%\.cloudflared" mkdir "%USERPROFILE%\.cloudflared"

REM Écrire la config (sans domaine = URL *.cfargotunnel.com automatique)
cloudflared tunnel info prixmaroc 2>&1

echo.
echo ════════════════════════════════════════════════════════
echo  VOTRE URL TUNNEL (permanente) :
cloudflared tunnel info prixmaroc 2>&1 | findstr "cfargotunnel"
echo ════════════════════════════════════════════════════════
echo.
echo Copiez cette URL et lancez le script 2_update_and_build.bat
echo.
pause
