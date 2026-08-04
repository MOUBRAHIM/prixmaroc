# PrixMaroc - Deploiement Railway
# Usage : PowerShell -ExecutionPolicy Bypass -File scripts\deploy_railway.ps1

param(
    [string]$Token = "",
    [string]$AnthropicKey = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# Railway CLI path (npm global sur Windows)
$RailwayCli = "$env:APPDATA\npm\railway.cmd"
if (-not (Test-Path $RailwayCli)) {
    $RailwayCli = "railway.cmd"  # Essai depuis le PATH
}
function Invoke-Railway {
    & $RailwayCli @args
}

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "       PrixMaroc - Deploiement Railway Cloud               " -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""

# -- 1. Token Railway ---------------------------------------------------------
if (-not $Token) {
    Write-Host "Token Railway requis." -ForegroundColor Yellow
    Write-Host "  -> Ouvre : https://railway.app/account/tokens" -ForegroundColor Cyan
    Write-Host "  -> Clique sur 'New Token', copie-le" -ForegroundColor Cyan
    Write-Host ""
    $Token = Read-Host "Colle ton token Railway ici"
}

if (-not $Token) {
    Write-Host "ERREUR : Token manquant." -ForegroundColor Red
    exit 1
}

$env:RAILWAY_TOKEN = $Token
Write-Host "  OK Token configure" -ForegroundColor Green
Write-Host ""

# -- 2. Cle Anthropic ----------------------------------------------------------
if (-not $AnthropicKey) {
    Write-Host "Cle Anthropic (Claude / IA) - optionnelle." -ForegroundColor Yellow
    Write-Host "  -> https://console.anthropic.com/settings/keys" -ForegroundColor Cyan
    Write-Host "  (Appuie ENTREE pour ignorer - les fonctions IA seront desactivees)" -ForegroundColor Gray
    $AnthropicKey = Read-Host "Cle Anthropic (sk-ant-...)"
}
Write-Host ""

# -- 3. Creer le projet Railway ------------------------------------------------
Write-Host "[1/6] Creation du projet Railway 'prixmaroc'..." -ForegroundColor Yellow
Set-Location (Join-Path $ProjectRoot "backend")

$existingProject = Invoke-Railwaystatus 2>&1
if ($existingProject -match "Project") {
    Write-Host "  OK Projet deja lie" -ForegroundColor Green
} else {
    Invoke-Railwayinit --name "prixmaroc" 2>&1
    Write-Host "  OK Projet cree" -ForegroundColor Green
}
Write-Host ""

# -- 4. Ajouter PostgreSQL -----------------------------------------------------
Write-Host "[2/6] Ajout PostgreSQL..." -ForegroundColor Yellow
Invoke-Railwayadd --plugin postgresql 2>&1
Write-Host "  OK PostgreSQL ajoute" -ForegroundColor Green
Start-Sleep 3
Write-Host ""

# -- 5. Ajouter Redis ----------------------------------------------------------
Write-Host "[3/6] Ajout Redis..." -ForegroundColor Yellow
Invoke-Railwayadd --plugin redis 2>&1
Write-Host "  OK Redis ajoute" -ForegroundColor Green
Start-Sleep 3
Write-Host ""

# -- 6. Variables d environnement ----------------------------------------------
Write-Host "[4/6] Configuration des variables..." -ForegroundColor Yellow

Invoke-Railwayvariables --set "SECRET_KEY=d3017a25aa0c4e97c6f99f40c614ec873c88d26120fc757b5e877a282a9976a3" 2>&1 | Out-Null
Invoke-Railwayvariables --set "ALGORITHM=HS256" 2>&1 | Out-Null
Invoke-Railwayvariables --set "ACCESS_TOKEN_EXPIRE_MINUTES=1440" 2>&1 | Out-Null
Invoke-Railwayvariables --set "ENVIRONMENT=production" 2>&1 | Out-Null
Invoke-Railwayvariables --set "DEBUG=false" 2>&1 | Out-Null
Invoke-Railwayvariables --set "LOG_LEVEL=WARNING" 2>&1 | Out-Null
Invoke-Railwayvariables --set "CORS_ORIGINS=*" 2>&1 | Out-Null
Invoke-Railwayvariables --set "PYTHONDONTWRITEBYTECODE=1" 2>&1 | Out-Null
Invoke-Railwayvariables --set "PYTHONUNBUFFERED=1" 2>&1 | Out-Null

if ($AnthropicKey) {
    Invoke-Railwayvariables --set "ANTHROPIC_API_KEY=$AnthropicKey" 2>&1 | Out-Null
    Write-Host "  OK ANTHROPIC_API_KEY configuree" -ForegroundColor Green
}

Write-Host "  OK Variables configurees" -ForegroundColor Green
Write-Host ""

# -- 7. Deploiement ------------------------------------------------------------
Write-Host "[5/6] Deploiement du backend (5-10 min)..." -ForegroundColor Yellow
Write-Host "  Upload du code vers Railway..." -ForegroundColor Gray
Invoke-Railwayup --detach 2>&1
Write-Host ""
Write-Host "  OK Code envoye - le build tourne sur Railway" -ForegroundColor Green
Write-Host ""

# -- 8. Recuperer l URL --------------------------------------------------------
Write-Host "[6/6] Generation de l URL publique..." -ForegroundColor Yellow
Start-Sleep 5

$domain = Invoke-Railwaydomain 2>&1
Write-Host "  Reponse : $domain" -ForegroundColor Gray

$apiUrl = ""
if ($domain -match "https://[a-z0-9\-]+\.up\.railway\.app") {
    $apiUrl = $Matches[0]
} else {
    Invoke-Railwaydomain --generate 2>&1 | Out-Null
    Start-Sleep 3
    $domain = Invoke-Railwaydomain 2>&1
    if ($domain -match "https://[a-z0-9\-]+\.up\.railway\.app") {
        $apiUrl = $Matches[0]
    } elseif ($domain -match "[a-z0-9\-]+\.up\.railway\.app") {
        $apiUrl = "https://" + $Matches[0]
    }
}

if ($apiUrl) {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  URL API : $apiUrl" -ForegroundColor White
    Write-Host "  Dashboard : https://railway.app/dashboard" -ForegroundColor White
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""

    # Mise a jour constants/index.ts
    Write-Host "Mise a jour de l URL dans l app mobile..." -ForegroundColor Yellow
    $ConstantsFile = Join-Path $ProjectRoot "mobile\src\constants\index.ts"
    $content = Get-Content $ConstantsFile -Raw

    # Remplacer l URL prod
    $content = $content -replace "ENV === 'prod'\s+\? 'https://[^']*'", "ENV === 'prod'   ? '$apiUrl'"
    # Passer en mode prod
    $content = $content -replace "= 'tunnel'", "= 'prod'"

    Set-Content $ConstantsFile $content -Encoding UTF8
    Write-Host "  OK constants/index.ts mis a jour -> ENV=prod, URL=$apiUrl" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Lance maintenant le build APK :" -ForegroundColor Yellow
    Write-Host "  cd mobile" -ForegroundColor Cyan
    Write-Host "  npx eas-cli build --platform android --profile preview" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "  URL non recuperee automatiquement." -ForegroundColor Yellow
    Write-Host "  Va sur https://railway.app/dashboard -> ton projet -> Settings -> Domain" -ForegroundColor Cyan
    Write-Host "  Puis donne-moi l URL et je mets a jour l app." -ForegroundColor White
}

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  Surveille : https://railway.app/dashboard" -ForegroundColor White
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
