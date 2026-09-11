<#
.SYNOPSIS
    Колонк POS — компьютер асах бүрд startup.bat-ыг өөрөө ажиллуулдаг болгоно.

.DESCRIPTION
    Task Scheduler-т «Kolonk POS - autostart» нэртэй ажил бүртгэнэ:

      * Хэрэглэгч нэвтрэхэд (30 секундийн дараа) start-dev.ps1-ийг
        startup.bat-тай яг ижил параметрээр (-Seed -Open -Quiet), гэхдээ
        цонхгүй далд горимоор ажиллуулна.
      * Цаг нь таараагүй асаалт (унтраад дахин асахад) StartWhenAvailable-ээр
        нөхөж ажиллана.

    АНХААР: Windows-ийн ажил хэрэглэгч НЭВТЭРСЭН үед л ажиллана.  Компьютер
    асаад нэвтрэх дэлгэц дээр зогсдог бол Sysinternals Autologon-оор автомат
    нэвтрэлт тохируулж өгнө:
    https://learn.microsoft.com/sysinternals/downloads/autologon

.PARAMETER Remove
    Бүртгэсэн ажлыг устгана (автомат асаалтыг болиулна).
#>

param([switch]$Remove)

$ErrorActionPreference = "Stop"
$Root     = $PSScriptRoot
$TaskName = "Kolonk POS - autostart"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "    '$TaskName' ажлыг устгалаа — автомат асаалт болилоо." -ForegroundColor Yellow
    exit 0
}

# Хуучин бүртгэл байвал сольж бичнэ (дахин ажиллуулахад аюулгүй).
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# startup.bat-ын хийдэг зүйлийг цонхгүй хийнэ: start-dev.ps1 -Seed -Open -Quiet
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Root\start-dev.ps1`" -Seed -Open -Quiet" `
    -WorkingDirectory $Root

# Нэвтрэхэд 30 секундийн дараа — сүлжээ, үйлчилгээнүүд амжиж асна.
$user    = "$env:USERDOMAIN\$env:USERNAME"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = "PT30S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Kolonk POS-iig computer asah bolgond ooroo asaana (start-dev.ps1 -Seed -Open -Quiet)." | Out-Null

Write-Host "    '$TaskName' бүртгэгдлээ:" -ForegroundColor Green
Write-Host "      - Хэрэглэгч нэвтэрснээс 30 секундийн дараа систем өөрөө асна" -ForegroundColor Gray
Write-Host "      - Лог: $Root\logs\" -ForegroundColor Gray
Write-Host "      - Болиулах: powershell -File register-startup.ps1 -Remove" -ForegroundColor Gray
