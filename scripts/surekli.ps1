# Yanki sürekli koşu: zamanlanmış görev (Görev Zamanlayıcı → Yanki\Surekli) bilgisayar açıkken her 30 dk çalıştırır
# (Scryne, 2026-10-10: "gece 3'ü beklemeye gerek yok, bilgisayar açıkken hep çalışsın"). Hangi adımın ne zaman
# koşacağına `yanki calistir` kendisi karar verir; iş yapılmayan koşu günlüğe hiçbir şey yazmaz. Düşen adımı `yanki
# calistir` kendisi bildirir (aynı hata günde bir kez); bu betik yalnız koşu hiç bitmediyse (çökme, başlatılamama)
# bildirir. Önce her sorunlu koşuda bildiriyordu: 2026-10-16'da düşen bir yükleme gün boyu 30 dk'da bir bildirim attı.
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
$script:bitti = $false  # "── koşu bitti" görüldü: adımların hatası Python tarafında bildirildi
# Başlık ilk çıktı satırında yazılır: hiçbir adım iş yapmadıysa günlükte iz kalmaz
# --no-sync: dinleme odası venv'i tutarken senkron düşmesin (oda.ps1 ile aynı gerekçe)
# Önceki koşu sürüyorsa (kiralık GPU'da üretim ~1 saat) her 30 dk'da "başka bir koşu sürüyor" yazılmasın: beklenen durum
& $uv run --no-sync python -m yanki calistir *>&1 | ForEach-Object {
    if (-not $script:basladi -and "$_" -like "başka bir yanki koşusu sürüyor*") { return }
    if (-not $script:basladi) {
        [IO.File]::AppendAllText($log, "=== $(Get-Date -Format s) başladı (sürekli)`r`n", $utf8)
        $script:basladi = $true
    }
    if ("$_" -like "── koşu bitti*") { $script:bitti = $true }
    [IO.File]::AppendAllText($log, "$_`r`n", $utf8)
}
$kod = $LASTEXITCODE
if ($script:basladi) { [IO.File]::AppendAllText($log, "=== $(Get-Date -Format s) bitti (kod $kod)`r`n", $utf8) }
if ($kod -ne 0 -and -not $script:bitti) {
    . (Join-Path $PSScriptRoot "bildirim.ps1")
    Bildir "Yanki: koşu hata verdi (kod $kod)" "Günlük: calisma\gunluk\$(Split-Path -Leaf $log)"
}
