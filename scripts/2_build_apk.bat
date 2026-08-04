@echo off
chcp 65001 >nul
title PrixMaroc — Build APK

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              PRIXMAROC — Génération APK                  ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo Ce script génère un fichier .apk installable sur
echo n'importe quel téléphone Android.
echo.

REM ── Vérifications préalables ─────────────────────────────────────────────────

echo [Vérification] Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERREUR: Node.js non trouvé. Installez-le depuis nodejs.org
    pause & exit /b 1
)

echo [Vérification] EAS CLI...
call npx eas-cli --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installation de EAS CLI...
    npm install -g eas-cli
)

REM ── Aller dans le dossier mobile ─────────────────────────────────────────────
cd /d "C:\Users\HP 840 G7\Desktop\PrixMaroc\mobile"

echo.
echo ════════════════════════════════════════════════════
echo  ÉTAPE 1 — Vérifiez l'URL de l'API dans le fichier :
echo  mobile\src\constants\index.ts
echo.
echo  Actuellement :
findstr "API_BASE_URL" "src\constants\index.ts" | findstr "ENV ==="
echo.
echo  Si l'URL est correcte, appuyez sur ENTRÉE pour continuer.
echo  Sinon, ouvrez le fichier et modifiez-le avant de continuer.
echo ════════════════════════════════════════════════════
pause

echo.
echo [ÉTAPE 2] Connexion à Expo...
echo Vous aurez besoin d'un compte Expo (gratuit sur expo.dev)
echo.
call npx eas-cli whoami 2>&1 | findstr "@" >nul
if %ERRORLEVEL% neq 0 (
    echo Connexion requise...
    call npx eas-cli login
)
echo.

echo [ÉTAPE 3] Lancement du build APK sur les serveurs EAS...
echo (durée estimée : 10-20 minutes — le build se fait dans le cloud)
echo.
echo Vous recevrez un lien de téléchargement par email.
echo.
call npx eas-cli build --platform android --profile preview --non-interactive

echo.
echo ════════════════════════════════════════════════════
echo  BUILD TERMINÉ !
echo.
echo  L'APK est disponible sur : https://expo.dev
echo  Ou téléchargez-le avec : eas build:list
echo.
echo  Pour installer sur un téléphone :
echo  1. Envoyez le fichier .apk par email / WhatsApp / USB
echo  2. Sur le téléphone : Réglages → Sécurité → Sources inconnues (ON)
echo  3. Ouvrez le fichier .apk téléchargé
echo ════════════════════════════════════════════════════
echo.
pause
