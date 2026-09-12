<#
.SYNOPSIS
    Хуучин нэр — install.ps1 -NoDocker руу дамжуулна.

.DESCRIPTION
    Суулгалт нэгдсэн install.bat / install.ps1-д нэгдсэн. Энэ файл README,
    TUNNEL-SETUP-ын хуучин холбоосууд болон ажилтнуудын дадал зуршлыг
    хадгалахын тулд үлдээв: яг ижил ажлыг install.ps1-ийн Docker-гүй зам хийнэ.
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$SkipStart)

$fw = @("-NoDocker")
if ($DryRun)   { $fw += "-DryRun" }
if ($SkipStart) { $fw += "-SkipStart" }
& (Join-Path $PSScriptRoot "install.ps1") @fw
exit $LASTEXITCODE
