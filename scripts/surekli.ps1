# Yanki sürekli koşu: zamanlanmış görev (Görev Zamanlayıcı → Yanki\Surekli) bilgisayar açıkken her 30 dk çalıştırır
# (Scryne, 2026-10-10: "gece 3'ü beklemeye gerek yok, bilgisayar açıkken hep çalışsın"). Hangi adımın ne zaman
# koşacağına `yanki calistir` kendisi karar verir; iş yapılmayan koşu günlüğe hiçbir şey yazmaz. Bildirim yalnız hata
# olunca (her şarkı olayı zaten kendi bildirimini gösteriyor; günlük özet 03:00 koşusunda, gece.ps1).
# Günlük: calisma/gunluk/<tarih>.log (gece koşusuyla aynı dosya)
$kok = Split-Path -Parent $PSScriptRoot
Set-Location $kok
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$gunluk = Join-Path $kok "calisma\gunluk"
New-Item -ItemType Directory -Force $gunluk | Out-Null
$log = Join-Path $gunluk ((Get-Date -Format "yyyy-MM-dd") + ".log")
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8
$script:basladi = $false
# Başlık ilk çıktı satırında yazılır: hiçbir adım iş yapmadıysa günlükte iz kalmaz
# --no-sync: dinleme odası venv'i tutarken senkron düşmesin (oda.ps1 ile aynı gerekçe)
& $uv run --no-sync python -m yanki calistir *>&1 | ForEach-Object {
    if (-not $script:basladi) {
        [IO.File]::AppendAllText($log, "=== $(Get-Date -Format s) başladı (sürekli)`r`n", $utf8)
        $script:basladi = $true
    }
    [IO.File]::AppendAllText($log, "$_`r`n", $utf8)
}
$kod = $LASTEXITCODE
if ($script:basladi) { [IO.File]::AppendAllText($log, "=== $(Get-Date -Format s) bitti (kod $kod)`r`n", $utf8) }
if ($kod -ne 0) {
    . (Join-Path $PSScriptRoot "bildirim.ps1")
    Bildir "Yanki: koşu hata verdi (kod $kod)" "Günlük: calisma\gunluk\$(Split-Path -Leaf $log)"
}
