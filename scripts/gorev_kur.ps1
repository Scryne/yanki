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
