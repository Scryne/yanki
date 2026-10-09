# Ortak Windows bildirimi (oda.ps1, gece.ps1). Tıklayınca $adres açılır (varsayılan dinleme odası).
function Bildir([string]$baslik, [string]$metin, [string]$adres = "http://127.0.0.1:8765/") {
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
    } catch { if (Get-Command Yaz -ErrorAction SilentlyContinue) { Yaz "bildirim gösterilemedi: $_" } }
}
