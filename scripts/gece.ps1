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
& $uv run yanki calistir *>&1 | ForEach-Object { [IO.File]::AppendAllText($log, "$_`r`n", $utf8) }
"=== $(Get-Date -Format s) bitti (kod $LASTEXITCODE)" | Add-Content $log -Encoding utf8
