<#
.SYNOPSIS
    PostgreSQL-ийн bin хавтсыг олох нийтлэг функц (dot-source-оор ашиглана).

.DESCRIPTION
    Урьд нь start-dev.ps1, backup-data.ps1, install-nodocker.ps1 гурвуулаа
    "C:\Program Files\PostgreSQL\17\bin" гэж хатуу заадаг байв. PostgreSQL 18
    суусан машин дээр native горим "олдсонгүй" гээд унадаг, суулгагч нь
    18-ын хажууд 17-г дахин суулгахыг оролддог байлаа.

    Дараалал:
      1. KOLONK_PGBIN орчны хувьсагч (гараар заах бол)
      2. C:\Program Files\PostgreSQL\<хувилбар>\bin — 17-г илүүд үзнэ
         (Docker-ын postgres:17 dump-тай нийцтэй), үгүй бол хамгийн шинэ
         16-аас дээш хувилбар.

    Ашиглах:
        . "$PSScriptRoot\pg-locate.ps1"
        $PgBin = Find-PgBin        # $null бол PostgreSQL суугаагүй
#>

function Find-PgBin {
    if ($env:KOLONK_PGBIN -and (Test-Path (Join-Path $env:KOLONK_PGBIN "pg_ctl.exe"))) {
        return $env:KOLONK_PGBIN
    }
    $base = Join-Path $env:ProgramFiles "PostgreSQL"
    if (-not (Test-Path $base)) { return $null }

    $versions = Get-ChildItem $base -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d+$' -and [int]$_.Name -ge 16 } |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\pg_ctl.exe") } |
        ForEach-Object { [int]$_.Name }

    if (-not $versions) { return $null }
    $pick = if ($versions -contains 17) { 17 } else { ($versions | Sort-Object -Descending)[0] }
    return (Join-Path $base "$pick\bin")
}

function Get-PgMajor([string]$PgBin) {
    if (-not $PgBin) { return $null }
    if ($PgBin -match 'PostgreSQL\\(\d+)\\bin') { return [int]$Matches[1] }
    return $null
}
