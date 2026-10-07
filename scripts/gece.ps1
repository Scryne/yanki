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
& $uv run yanki calistir *>&1 | ForEach-Object { "$_" } | Add-Content $log -Encoding utf8
"=== $(Get-Date -Format s) bitti (kod $LASTEXITCODE)" | Add-Content $log -Encoding utf8
