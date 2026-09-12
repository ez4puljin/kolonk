<#
.SYNOPSIS
    Колонк POS — Docker-той станцад watchdog.ps1-ийг Task Scheduler-т бүртгэнэ.

.DESCRIPTION
    «Kolonk POS - watchdog» нэртэй ажил:
      * Хэрэглэгч нэвтэрснээс 1 минутын дараа эхэлж, дараа нь 5 минут тутам
        watchdog.ps1-ийг цонхгүй ажиллуулна.
      * watchdog нь Docker engine унтарсан бол Docker Desktop-ыг асааж,
        prod + tunnel профайлын дутуу контейнерийг өргөнө.

    Яагаад хэрэгтэй вэ: Docker Desktop-ын Run бүртгэл GUI-г асаадаг ч engine
    заавал асдаггүй; компьютер дахин ачаалагдахад систем унтарсан хэвээр
    үлддэг. 2026-09 сард яг ийм шалтгаанаар сайт нэг өдөр ажиллаагүй.

    АНХААР: ажил хэрэглэгч НЭВТЭРСЭН үед л явна — нэвтрэх дэлгэц дээр зогсдог
    бол Sysinternals Autologon-оор автомат нэвтрэлт тохируулна.

.PARAMETER Remove
    Бүртгэсэн ажлыг устгана.
#>

param([switch]$Remove)

$ErrorActionPreference = "Stop"
$Root     = $PSScriptRoot
$TaskName = "Kolonk POS - watchdog"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "    '$TaskName' ажлыг устгалаа." -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Root\watchdog.ps1`"" `
    -WorkingDirectory $Root

$user    = "$env:USERDOMAIN\$env:USERNAME"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay              = "PT1M"
$trigger.Repetition         = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Docker engine/konteiner untarval 5 minut tutam ooroo sergeene (watchdog.ps1)." | Out-Null

Write-Host "    '$TaskName' бүртгэгдлээ:" -ForegroundColor Green
Write-Host "      - Нэвтэрснээс 1 минутын дараа, цаашид 5 минут тутам" -ForegroundColor Gray
Write-Host "      - Лог: $Root\logs\watchdog.log" -ForegroundColor Gray
Write-Host "      - Болиулах: powershell -File register-watchdog.ps1 -Remove" -ForegroundColor Gray
