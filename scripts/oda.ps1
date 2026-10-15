# Yanki dinleme odası: oturum açılınca zamanlanmış görev (Görev Zamanlayıcı → Yanki\Oda) bunu çalıştırır.
# Odayı arka planda 127.0.0.1:8765'te açar (tarayıcı açmaz), hattın özetini Windows bildirimiyle gösterir; bildirime
# tıklayınca oda açılır. Oda zaten açıksa (Kokpit ya da elle `yanki dinle`) yalnız bildirimi gösterir.
# Günlük: calisma/gunluk/oda.log
param([int]$Port = 8765)
$kok = Split-Path -Parent $PSScriptRoot
Set-Location $kok
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$gunluk = Join-Path $kok "calisma\gunluk"
New-Item -ItemType Directory -Force $gunluk | Out-Null
$log = Join-Path $gunluk "oda.log"
# günlük sınırsız büyümesin (2026-10-10: 227 KB, çoğu izleme satırı): 5 MB'ı geçince .1'e döner
if ((Test-Path $log) -and (Get-Item $log).Length -gt 5MB) { Move-Item $log "$log.1" -Force }
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8
function Yaz($m) { [IO.File]::AppendAllText($log, "$(Get-Date -Format s) $m`r`n", $utf8) }
$adres = "http://127.0.0.1:$Port/"

. (Join-Path $PSScriptRoot "bildirim.ps1")  # Bildir: ortak Windows bildirimi

$acik = $false
try { $acik = (Invoke-WebRequest "${adres}api/sarkilar" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
$ozet = (& $uv run --no-sync python -m yanki ozet 2>$null) -join " "
Yaz "özet: $ozet"
Bildir "Yanki" $ozet
if ($acik) { Yaz "oda zaten açık: $adres"; exit 0 }
Yaz "oda başlıyor: $adres"
# yanki.exe değil python -m: açık oda yanki.exe'yi kilitler, bağımlılık değişince gece koşusunun `uv run` senkronu düşer
& $uv run --no-sync python -m yanki dinle --tarayicisiz --port $Port *>&1 | ForEach-Object { [IO.File]::AppendAllText($log, "$_`r`n", $utf8) }
Yaz "oda kapandı (kod $LASTEXITCODE)"
