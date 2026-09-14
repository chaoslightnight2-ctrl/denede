Set-Location -Path $PSScriptRoot
$ErrorActionPreference = "Continue"
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }

# Günlük tek çalıştırma kilidi: bugün başarılı yükleme olduysa çık.
$marker = Join-Path $PSScriptRoot "last_upload_date.txt"
$today = Get-Date -Format "yyyy-MM-dd"
if ((Test-Path $marker) -and ((Get-Content $marker -Raw).Trim() -eq $today)) {
    exit 0
}

$log = Join-Path $PSScriptRoot ("logs\run_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

# 3 deneme (ağ/antivirüs TLS gecikmesine karşı).
# -u: loglar crash anında bile dosyaya düşer.
$code = 1
for ($i = 1; $i -le 3 -and $code -ne 0; $i++) {
    "==== deneme $i, saat $(Get-Date -Format HH:mm:ss) ====" | Out-File -FilePath $log -Append -Encoding utf8
    & "$PSScriptRoot\.venv\Scripts\python.exe" -u -m src.pipeline >> $log 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $i -lt 3) { Start-Sleep -Seconds 60 }
}

# Sadece başarıda işaretle, başarısız gün ertesi girişte tekrar dener.
if ($code -eq 0) { Set-Content -Path $marker -Value $today -NoNewline -Encoding utf8 }
exit $code
