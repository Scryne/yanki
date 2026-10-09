# Yanki\Gece zamanlanmış görevini kurar ya da günceller (her gece 03:00, pilde başlamaz). Bir kez çalıştır.
# Ders (2026-10-08): pwsh.exe (Store sürümü) zamanlayıcıda bulunamadı (0x80070002); -WindowStyle Hidden
# Windows 11'in varsayılan terminali (Windows Terminal) ile pencereyi gizlemiyor ve pencere kapanınca motor
# "window-CLOSE event" ile ölüyor. Bu yüzden: yerleşik powershell.exe, pencere açmayan conhost --headless içinde.
$kok = Split-Path -Parent $PSScriptRoot
$ps = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$arg = "--headless `"$ps`" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$kok\scripts\gece.ps1`""
$eylem = New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR "System32\conhost.exe") -Argument $arg -WorkingDirectory $kok
$zaman = New-ScheduledTaskTrigger -Daily -At 03:00
$ayar = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 8) `
    -MultipleInstances IgnoreNew  # pil: varsayılan olarak pilde başlamaz, pile geçince durur
$kim = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskPath "\Yanki\" -TaskName "Gece" -Action $eylem -Trigger $zaman -Settings $ayar `
    -Principal $kim -Force | Out-Null
"Yanki\Gece kuruldu: her gece 03:00 → $kok\scripts\gece.ps1"

# Yanki\Oda: oturum açılınca dinleme odası arka planda (127.0.0.1:8765) + özet bildirimi (Scryne, 2026-10-09:
# "bilgisayar açıldığında yanki otomatik başlasın"). Süre sınırı yok; düşerse 1 dk arayla 3 kez yeniden başlar.
$arg = "--headless `"$ps`" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$kok\scripts\oda.ps1`""
$eylem = New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR "System32\conhost.exe") -Argument $arg -WorkingDirectory $kok
$zaman = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$zaman.Delay = "PT45S"  # oturum açılışındaki yükü beklesin (ağ, Defender taraması)
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskPath "\Yanki\" -TaskName "Oda" -Action $eylem -Trigger $zaman -Settings $ayar `
    -Principal $kim -Force | Out-Null
"Yanki\Oda kuruldu: oturum açılınca → $kok\scripts\oda.ps1 (http://127.0.0.1:8765/)"

# Yanki\Gunduz: gündüz boşta üretim (Roadmap Faz 13). 08:00'den itibaren 17 saat boyunca her 30 dk; koşulları
# `yanki gunduz` denetler (saat penceresi, 20 dk boşta, priz, GPU). Pilde başlamaz; 2 saatten uzun sürerse durdurulur.
$arg = "--headless `"$ps`" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$kok\scripts\gunduz.ps1`""
$eylem = New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR "System32\conhost.exe") -Argument $arg -WorkingDirectory $kok
$zaman = New-ScheduledTaskTrigger -Daily -At 08:00
$zaman.Repetition = (New-ScheduledTaskTrigger -Once -At 08:00 -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 17)).Repetition
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskPath "\Yanki\" -TaskName "Gunduz" -Action $eylem -Trigger $zaman -Settings $ayar `
    -Principal $kim -Force | Out-Null
"Yanki\Gunduz kuruldu: 08:00–01:00 her 30 dk → $kok\scripts\gunduz.ps1"
