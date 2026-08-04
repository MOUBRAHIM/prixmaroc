# ============================================================================
#  PrixMaroc — Démarrage LOCAL pour test mobile (Expo Go + QR)
#
#  Ce script :
#    1. Lance le backend FastAPI (nouvelle fenêtre) sur http://0.0.0.0:8000
#       → utilise la vraie base Neon (données déjà seedées)
#    2. Lance le serveur Expo (dans cette fenêtre) → affiche un QR CODE
#       → scanne-le avec l'app "Expo Go" sur ton téléphone (même WiFi)
#
#  Prérequis : téléphone et PC sur le MÊME réseau WiFi.
#  Usage :  clic droit → "Exécuter avec PowerShell"   (ou :  ./start-local.ps1)
# ============================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "=== PrixMaroc — mode test LOCAL ===" -ForegroundColor Green
Write-Host "IP de ton PC (à retrouver dans le QR) : 192.168.0.116" -ForegroundColor Cyan
Write-Host ""

# 1) Backend dans une nouvelle fenêtre PowerShell
Write-Host "-> Démarrage du backend (nouvelle fenêtre)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root\backend'; python run_local.py"
)

# Laisse le backend démarrer
Start-Sleep -Seconds 5

# 2) Expo dans cette fenêtre (le QR s'affiche ici)
Write-Host "-> Démarrage d'Expo (le QR va s'afficher ci-dessous)..." -ForegroundColor Yellow
Write-Host "   Scanne le QR avec l'app Expo Go sur ton téléphone." -ForegroundColor Cyan
Write-Host ""
Set-Location "$root\mobile"

# LAN par défaut ; si le QR ne se charge pas sur le tel, relance avec :  npx expo start --tunnel
npx expo start --clear
