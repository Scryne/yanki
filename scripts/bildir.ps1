# Tek bildirim: yanki/olay.py kaydı tutar ve bunu çağırır; bu betik yalnız gösterir.
param([string]$Baslik, [string]$Metin, [string]$Adres = "http://127.0.0.1:8765/")
function Yaz($m) { [Console]::Error.WriteLine($m) }  # Bildir hatayı buraya yazar (sessiz kalmasın)
. (Join-Path $PSScriptRoot "bildirim.ps1")
Bildir $Baslik $Metin $Adres
