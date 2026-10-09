# Yanki gündüz boşta üretim: zamanlanmış görev (Görev Zamanlayıcı → Yanki\Gunduz) her 30 dk çalıştırır.
# Koşulları `yanki gunduz` kendisi denetler (saat, boşta kalma, priz, GPU, iş var mı) ve uymuyorsa tek satırla çıkar.
# Günlük: calisma/gunluk/gunduz.log (1 MB'ı geçince .1'e döner)
$kok = Split-Path -Parent $PSScriptRoot
Set-Location $kok
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$gunluk = Join-Path $kok "calisma\gunluk"
New-Item -ItemType Directory -Force $gunluk | Out-Null
$log = Join-Path $gunluk "gunduz.log"
if ((Test-Path $log) -and (Get-Item $log).Length -gt 1MB) { Move-Item $log "$log.1" -Force }
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8
$an = Get-Date -Format s
# yanki.exe değil python -m (oda.ps1 ile aynı gerekçe); --no-sync: açık oda venv'i tutarken senkron düşmesin
& $uv run --no-sync python -m yanki gunduz *>&1 | ForEach-Object { [IO.File]::AppendAllText($log, "$an $_`r`n", $utf8) }
