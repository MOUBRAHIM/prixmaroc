# PrixMaroc — Démarrage tunnel + mise à jour URL automatique
# Usage: PowerShell -ExecutionPolicy Bypass -File scripts\start_tunnel_and_update.ps1

param(
    [switch]$Build  # Ajouter -Build pour lancer EAS Build après
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConstantsFile = Join-Path $ProjectRoot "mobile\src\constants\index.ts"
$TunnelLog = Join-Path $env:TEMP "prixmaroc_tunnel.log"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          PrixMaroc — Tunnel + Mise à jour URL            ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# ── 1. Arrêter les anciens tunnels ───────────────────────────────────────────
Write-Host "[1/4] Arrêt des anciens tunnels cloudflared..." -ForegroundColor Yellow
Get-Process "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

# ── 2. Démarrer le tunnel et capturer l'URL ──────────────────────────────────
Write-Host "[2/4] Démarrage du tunnel Cloudflare..." -ForegroundColor Yellow
Remove-Item $TunnelLog -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath "cloudflared" `
    -ArgumentList "tunnel --url http://localhost:8000" `
    -RedirectStandardError $TunnelLog `
    -PassThru -WindowStyle Hidden

# Attendre que l'URL apparaisse dans les logs (max 20s)
$tunnelUrl = $null
$timeout = 20
$elapsed = 0
while (-not $tunnelUrl -and $elapsed -lt $timeout) {
    Start-Sleep 1
    $elapsed++
    if (Test-Path $TunnelLog) {
        $content = Get-Content $TunnelLog -Raw -ErrorAction SilentlyContinue
        if ($content -match "https://([a-z0-9\-]+\.trycloudflare\.com)") {
            $tunnelUrl = "https://" + $Matches[1]
        }
    }
    Write-Host "  Attente URL... ($elapsed/$timeout)" -ForegroundColor Gray -NoNewline
    Write-Host "`r" -NoNewline
}

if (-not $tunnelUrl) {
    Write-Host "ERREUR: Impossible d'obtenir l'URL du tunnel." -ForegroundColor Red
    Write-Host "Vérifiez que Docker est démarré et que le backend fonctionne." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  URL TUNNEL (valide jusqu'au prochain redémarrage PC) :  ║" -ForegroundColor Cyan
Write-Host "║  $tunnelUrl" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 3. Mettre à jour constants/index.ts ──────────────────────────────────────
Write-Host "[3/4] Mise à jour de l'URL dans l'app..." -ForegroundColor Yellow

$content = Get-Content $ConstantsFile -Raw
# Remplacer l'URL du tunnel (pattern flexible)
$newContent = $content -replace "ENV === 'tunnel' \? 'https://[^']*\.trycloudflare\.com'", "ENV === 'tunnel' ? '$tunnelUrl'"
Set-Content $ConstantsFile $newContent -Encoding UTF8

Write-Host "  ✓ $ConstantsFile mis à jour" -ForegroundColor Green
Write-Host "  ✓ Nouvelle URL: $tunnelUrl" -ForegroundColor Green
Write-Host ""

# ── 4. Build optionnel ───────────────────────────────────────────────────────
if ($Build) {
    Write-Host "[4/4] Lancement EAS Build..." -ForegroundColor Yellow
    Set-Location (Join-Path $ProjectRoot "mobile")

    Write-Host "  Vérification connexion Expo..." -ForegroundColor Gray
    npx eas-cli whoami 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Connexion à Expo requise..." -ForegroundColor Yellow
        npx eas-cli login
    }

    Write-Host "  Lancement du build APK (10-20 min)..." -ForegroundColor Yellow
    npx eas-cli build --platform android --profile preview
} else {
    Write-Host "[4/4] Build APK non demandé (ajoutez -Build pour builder)." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Pour builder l'APK maintenant :" -ForegroundColor White
    Write-Host "  cd mobile && npx eas-cli build --platform android --profile preview" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Tunnel actif sur: $tunnelUrl" -ForegroundColor Green
Write-Host "  Gardez cette fenêtre PowerShell ouverte !" -ForegroundColor Yellow
Write-Host "  (Le tunnel s'arrête si vous fermez cette fenêtre)" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Garder le script actif
Write-Host "Appuyez sur Ctrl+C pour arrêter le tunnel." -ForegroundColor Gray
try { Wait-Process -Id $proc.Id } catch { }
