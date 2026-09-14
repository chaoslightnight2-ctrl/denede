$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
  Write-Host "Sanal ortam kuruluyor..."
  py -3 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host ".env oluşturuldu — API anahtarlarını yaz."
}

New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "output" | Out-Null

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Warning "ffmpeg PATH'te yok. Kur: winget install Gyan.FFmpeg"
}

if (-not (Test-Path "client_secret.json")) {
  Write-Warning "client_secret.json yok. Google Cloud Console -> YouTube Data API v3 -> OAuth Desktop kimliği indirip bu klasöre koy."
}

Write-Host ""
Write-Host "Kurulum tamam. Sıradakiler:"
Write-Host "  1. .env içine API anahtarlarını yaz"
Write-Host "  2. client_secret.json dosyasını bu klasöre koy (OAuth desktop)"
Write-Host "  3. İlk çalıştırma (yüklemez): .\.venv\Scripts\python.exe -m src.pipeline --no-upload"
Write-Host "  4. Gerçek çalıştırma:        .\run_daily.ps1"
