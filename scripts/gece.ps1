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
# Satır satır aç-yaz-kapa: Windows PowerShell 5.1'de boru hattındaki Add-Content dosyayı koşu boyunca kilitliyor
# (Add-Content -Encoding utf8 yeni dosyanın başına BOM da koyuyordu: 2026-10-10.log)
$utf8 = New-Object System.Text.UTF8Encoding $false
function Yaz($m) { [IO.File]::AppendAllText($log, "$m`r`n", $utf8) }
Yaz "=== $(Get-Date -Format s) başladı"
[Console]::OutputEncoding = $utf8  # Python UTF-8 yazar (PYTHONUTF8); 5.1 varsayılan OEM 857 ile okuyup bozuyordu
# 03:00'te sürekli koşu (\Yanki\Surekli, 30 dk'da bir) çoğu zaman kilidi önce alıyor (iki görev aynı anda tetikleniyor).
# Önce gece koşusu hemen çıkıyordu, sabah özeti hiç gelmiyordu: şimdi o koşunun bitmesini bekler (dakikada bir, en çok
# 3 saat), sonra kendisi koşar (zamanı gelmiş adım kalmadıysa hızlıca biter) ve özeti gösterir.
# --no-sync + python -m (surekli.ps1, oda.ps1 ile aynı): açık dinleme odası venv'i ve yanki.exe'yi tutarken `uv run`
# senkronu düşüyor, gece koşusu hiç başlamıyordu
$deneme = 0
do {
    $cikti = New-Object System.Collections.Generic.List[string]
    & $uv run --no-sync python -m yanki calistir *>&1 | ForEach-Object {
        $cikti.Add("$_")
        if ("$_" -notlike "başka bir yanki koşusu sürüyor*") { Yaz "$_" } }
    $kod = $LASTEXITCODE
    $mesgul = [bool]($cikti -like "başka bir yanki koşusu sürüyor*")
    if ($mesgul) {
        if ($deneme -eq 0) { Yaz "=== $(Get-Date -Format s) sürekli koşu sürüyor; bitince gece koşusu yeniden denenecek" }
        $deneme++
        if ($deneme -ge 180) { Yaz "=== $(Get-Date -Format s) sürekli koşu 3 saatte bitmedi, gece koşusu bıraktı"; exit 0 }
        Start-Sleep -Seconds 60
    }
} while ($mesgul)
Yaz "=== $(Get-Date -Format s) bitti (kod $kod)"
# Sonuç bildirimi (bilgisayar gece açıksa sabah bildirim merkezinde durur). Düşen adımın kendisi `yanki calistir`
# tarafından ayrıca bildirilir; koşu hiç bitmediyse (çökme) yalnız burada.
. (Join-Path $PSScriptRoot "bildirim.ps1")
$bitti = [bool]($cikti -like "── koşu bitti*")
$ozet = (& $uv run --no-sync python -m yanki ozet 2>$null) -join " "
if ($kod -ne 0 -and -not $bitti) { Bildir "Yanki: gece koşusu hata verdi (kod $kod)" "Günlük: calisma\gunluk\$(Split-Path -Leaf $log)" }
elseif ($kod -ne 0) { Bildir "Yanki: gece koşusu bitti, sorunlu adım var" $ozet }
else { Bildir "Yanki: gece koşusu bitti" $ozet }
