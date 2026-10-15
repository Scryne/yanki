# Yanki gece koşusu: zamanlanmış görev (Görev Zamanlayıcı → Yanki\Gece) bunu çalıştırır.
# Listeyi hazırlar, adayları ve bekleyen onarımları üretir, onaylıları paketler. Çıktı: calisma/gunluk/<tarih>.log
$kok = Split-Path -Parent $PSScriptRoot
Set-Location $kok
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"  # günlük satırları anında düşsün (boruya yazınca Python tamponluyor)
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$gunluk = Join-Path $kok "calisma\gunluk"
New-Item -ItemType Directory -Force $gunluk | Out-Null
$log = Join-Path $gunluk ((Get-Date -Format "yyyy-MM-dd") + ".log")
"=== $(Get-Date -Format s) başladı" | Add-Content $log -Encoding utf8
# Satır satır aç-yaz-kapa: Windows PowerShell 5.1'de boru hattındaki Add-Content dosyayı koşu boyunca kilitliyor
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8  # Python UTF-8 yazar (PYTHONUTF8); 5.1 varsayılan OEM 857 ile okuyup bozuyordu
# --no-sync + python -m (surekli.ps1, oda.ps1 ile aynı): açık dinleme odası venv'i ve yanki.exe'yi tutarken `uv run`
# senkronu düşüyor, gece koşusu hiç başlamıyordu
$cikti = New-Object System.Collections.Generic.List[string]
& $uv run --no-sync python -m yanki calistir *>&1 | ForEach-Object {
    $cikti.Add("$_"); [IO.File]::AppendAllText($log, "$_`r`n", $utf8) }
$kod = $LASTEXITCODE
# 03:00'te sürekli koşu (\Yanki\Surekli, 30 dk'da bir) çoğu zaman kilidi önce alıyor: bu koşu hiçbir şey yapmadı,
# iş o koşuda yapılıyor. "Gece koşusu bitti" bildirimi gösterilmez.
if ($cikti -match "başka bir yanki koşusu sürüyor") {
    "=== $(Get-Date -Format s) sürekli koşu sürüyordu, gece koşusu onu bıraktı" | Add-Content $log -Encoding utf8
    exit 0
}
"=== $(Get-Date -Format s) bitti (kod $kod)" | Add-Content $log -Encoding utf8
# Sonuç bildirimi (bilgisayar gece açıksa sabah bildirim merkezinde durur)
. (Join-Path $PSScriptRoot "bildirim.ps1")
if ($kod -ne 0) { Bildir "Yanki: gece koşusu hata verdi (kod $kod)" "Günlük: calisma\gunluk\$(Split-Path -Leaf $log)" }
else { Bildir "Yanki: gece koşusu bitti" ((& $uv run --no-sync python -m yanki ozet 2>$null) -join " ") }
