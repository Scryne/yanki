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
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8
function Yaz($m) { [IO.File]::AppendAllText($log, "$(Get-Date -Format s) $m`r`n", $utf8) }
$adres = "http://127.0.0.1:$Port/"

function Bildir([string]$baslik, [string]$metin) {
    # Windows PowerShell 5.1 WinRT bildirimi; modül gerektirmez. Uygulama kimliği PowerShell'in (Başlat'ta kayıtlı).
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $esc = [Security.SecurityElement]
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml("<toast activationType=`"protocol`" launch=`"$adres`"><visual><binding template=`"ToastGeneric`">" +
            "<text>$($esc::Escape($baslik))</text><text>$($esc::Escape($metin))</text></binding></visual></toast>")
        $kimlik = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($kimlik).Show(
            [Windows.UI.Notifications.ToastNotification]::new($xml))
    } catch { Yaz "bildirim gösterilemedi: $_" }
}

$acik = $false
try { $acik = (Invoke-WebRequest "$adres`api/sarkilar" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
$ozet = (& $uv run --no-sync python -m yanki ozet 2>$null) -join " "
Yaz "özet: $ozet"
Bildir "Yanki" $ozet
if ($acik) { Yaz "oda zaten açık: $adres"; exit 0 }
Yaz "oda başlıyor: $adres"
# yanki.exe değil python -m: açık oda yanki.exe'yi kilitler, bağımlılık değişince gece koşusunun `uv run` senkronu düşer
& $uv run --no-sync python -m yanki dinle --tarayicisiz --port $Port *>&1 | ForEach-Object { [IO.File]::AppendAllText($log, "$_`r`n", $utf8) }
Yaz "oda kapandı (kod $LASTEXITCODE)"
