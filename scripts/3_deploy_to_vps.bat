@echo off
chcp 65001 >nul
title PrixMaroc — Déploiement VPS

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         PRIXMAROC — Déploiement sur VPS                  ║
echo ║   L'app fonctionnera sans PC ni tunnel après ça !        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo PRÉREQUIS :
echo   1. Un VPS Ubuntu 22.04 loué (Hetzner/OVH/DigitalOcean)
echo   2. L'IP du VPS sous la main
echo   3. Ta clé Anthropic (console.anthropic.com)
echo.
echo ════════════════════════════════════════════════════════════

set /p VPS_IP="IP de ton VPS (ex: 65.21.123.45) : "
set /p VPS_USER="Utilisateur SSH (généralement 'root') : "
set /p ANTHROPIC_KEY="Clé Anthropic API (sk-ant-...) : "

echo.
echo [1/5] Vérification connexion SSH...
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no %VPS_USER%@%VPS_IP% "echo OK" 2>&1
if errorlevel 1 (
    echo.
    echo ERREUR : Impossible de se connecter au VPS.
    echo Vérifie que :
    echo   - L'IP est correcte
    echo   - Le port 22 est ouvert
    echo   - Tu as une clé SSH configurée ou utilise le mot de passe
    pause
    exit /b 1
)
echo OK Connexion SSH réussie

echo.
echo [2/5] Mise à jour de la clé Anthropic dans .env.production...
cd /d "C:\Users\HP 840 G7\Desktop\PrixMaroc"
powershell -Command "(Get-Content backend\.env.production) -replace 'ANTHROPIC_API_KEY=.*', 'ANTHROPIC_API_KEY=%ANTHROPIC_KEY%' | Set-Content backend\.env.production"
powershell -Command "(Get-Content backend\.env.production) -replace 'http://TON_IP_VPS', 'http://%VPS_IP%' | Set-Content backend\.env.production"
echo OK Fichier .env.production mis à jour

echo.
echo [3/5] Installation de Docker sur le VPS...
ssh -o StrictHostKeyChecking=no %VPS_USER%@%VPS_IP% "curl -fsSL https://get.docker.com | sh && systemctl enable docker && systemctl start docker"
echo OK Docker installé

echo.
echo [4/5] Copie du projet sur le VPS...
ssh %VPS_USER%@%VPS_IP% "mkdir -p /opt/prixmaroc"
scp -r "C:\Users\HP 840 G7\Desktop\PrixMaroc\backend" %VPS_USER%@%VPS_IP%:/opt/prixmaroc/
scp -r "C:\Users\HP 840 G7\Desktop\PrixMaroc\nginx" %VPS_USER%@%VPS_IP%:/opt/prixmaroc/
scp "C:\Users\HP 840 G7\Desktop\PrixMaroc\docker-compose.prod.yml" %VPS_USER%@%VPS_IP%:/opt/prixmaroc/
echo OK Fichiers copiés

echo.
echo [5/5] Démarrage des services sur le VPS...
ssh %VPS_USER%@%VPS_IP% "cd /opt/prixmaroc && docker compose -f docker-compose.prod.yml up -d db redis && sleep 10 && docker compose -f docker-compose.prod.yml up -d backend"
echo.
echo Attente démarrage backend (30s)...
timeout /t 30 /nobreak >nul
ssh %VPS_USER%@%VPS_IP% "curl -s http://localhost:8000/health"

echo.
echo ════════════════════════════════════════════════════════════
echo  ✅ DÉPLOIEMENT TERMINÉ !
echo.
echo  API accessible sur : http://%VPS_IP%:8000
echo  (Teste dans le navigateur : http://%VPS_IP%:8000/health)
echo.
echo  PROCHAINE ÉTAPE :
echo  Mets à jour l'app mobile pour utiliser cette URL permanente :
echo.
echo  Dans mobile\src\constants\index.ts :
echo    const ENV = 'prod'  ← changer tunnel par prod
echo    'http://%VPS_IP%:8000'  ← mettre cette IP dans la ligne prod
echo.
echo  Puis relance un build APK.
echo ════════════════════════════════════════════════════════════
echo.
pause
