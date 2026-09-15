<#
.SYNOPSIS
    Kolonk POS — Docker болон системийн автомат сэргээлт (watchdog).

.DESCRIPTION
    Docker Desktop-ын engine унтарсан бол асааж, дараа нь prod + tunnel
    профайлыг өргөнө. Task Scheduler-ээс 5 минут тутам дуудагдана.

    Яагаад хэрэгтэй вэ: Docker Desktop-ын `AutoStart` тохиргоо унтраатай
    үед Run бүртгэл GUI-г асаадаг ч engine асдаггүй. Мөн компьютер дахин
    ачаалагдахад систем унтарсан хэвээр үлддэг.

.PARAMETER TimeoutMinutes
    Engine асахыг хүлээх дээд хугацаа (өгөгдмөл 5).
#>
param([int]$TimeoutMinutes = 5)

$ErrorActionPreference = 'Continue'
$Root   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir 'watchdog.log'

# Лог хэт томрохоос сэргийлж 1 МБ давбал хагасыг нь таслана.
if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 1MB)) {
    $keep = Get-Content $LogFile -Tail 2000
    Set-Content -Path $LogFile -Value $keep -Encoding utf8
}

function Write-Log([string]$Msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Test-Engine {
    $null = & docker info --format '{{.ServerVersion}}' 2>$null
    return ($LASTEXITCODE -eq 0)
}

# --- 1. Engine шалгах, шаардвал Docker Desktop асаах ----------------------
if (-not (Test-Engine)) {
    Write-Log 'Docker engine хариу өгөхгүй байна — Docker Desktop асааж байна.'

    # Machine-wide ба per-user (админ эрхгүй суулгасан) байрлалууд + registry.
    # Урьд нь зөвхөн Program Files-ийг шалгадаг байсан тул %LOCALAPPDATA%-д
    # суусан Docker-той станц дээр watchdog "олдсонгүй" гээд юу ч хийдэггүй байв.
    $roots = @(
        "$env:ProgramFiles\Docker\Docker",
        "$env:LOCALAPPDATA\Programs\DockerDesktop",
        "$env:LOCALAPPDATA\Programs\Docker\Docker",
        "$env:LOCALAPPDATA\Docker"
    )
    foreach ($rk in 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop',
                   'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop') {
        $loc = (Get-ItemProperty $rk -ErrorAction SilentlyContinue).InstallLocation
        if ($loc) { $roots = @($loc) + $roots }
    }
    $exe = $roots | ForEach-Object { Join-Path $_ 'Docker Desktop.exe' } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) { Write-Log 'ЗОГСЛОО: Docker Desktop.exe олдсонгүй (Program Files / LocalAppData / registry).'; exit 1 }

    # com.docker.service нь privileged туслах — эхлээд түүнийг босгоно.
    $svc = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        try { Start-Service 'com.docker.service' -ErrorAction Stop; Write-Log 'com.docker.service асаав.' }
        catch { Write-Log "com.docker.service асаахад алдаа: $($_.Exception.Message)" }
    }

    if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        Start-Process $exe
    }

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 10
        if (Test-Engine) { break }
    }

    if (-not (Test-Engine)) {
        Write-Log "ЗОГСЛОО: engine $TimeoutMinutes минутын дотор асаагүй."
        exit 1
    }
    Write-Log 'Docker engine бэлэн боллоо.'
}

# --- 1b. Docker Desktop «Pause» төлөвт байвал (Whale цэснээс санамсаргүй) ---
# Engine хариу өгдөг ч контейнер ажиллахгүй, compose «manually paused» алдаа
# өгнө. 2026-09-15 яг ийм шалтгаанаар бүх контейнер зогсож, watchdog 5 минут
# тутам дэмий оролдож байв. `docker desktop restart` л буцааж асаана.
$dstatus = (& docker desktop status 2>$null | Out-String)
if ($dstatus -match 'Status\s+paused') {
    Write-Log 'Docker Desktop зогсоолттой (paused) байна — restart хийж байна.'
    & docker desktop restart 2>$null | Out-Null
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 10
        $dstatus = (& docker desktop status 2>$null | Out-String)
        if ($dstatus -match 'Status\s+running' -and (Test-Engine)) { break }
    }
    Write-Log ('Docker Desktop төлөв: {0}' -f (($dstatus -replace '\s+', ' ').Trim()))
}

# --- 2. Контейнерууд бүрэн эсэхийг шалгах --------------------------------
$expected = @('kolonk-db-1','kolonk-redis-1','kolonk-api-prod-1',
              'kolonk-worker-1','kolonk-nginx-1')
# cloudflared зөвхөн .env-д TUNNEL_TOKEN байгаа станцад л ажилладаг. Токенгүй
# станцад түүнийг "дутуу" гэж тооцвол 5 минут тутам дэмий сэргээх гэж оролдоно.
$envFile = Join-Path $Root '.env'
if ((Test-Path $envFile) -and ((Get-Content $envFile) -match '^TUNNEL_TOKEN=eyJ')) {
    $expected += 'kolonk-cloudflared-1'
}

$running = @(& docker ps --format '{{.Names}}' 2>$null)
$missing = @($expected | Where-Object { $running -notcontains $_ })

if ($missing.Count -eq 0) { exit 0 }

Write-Log ("Дутуу контейнер: {0} — өргөж байна." -f ($missing -join ', '))
Push-Location $Root
try {
    $out = & docker compose --profile prod --profile tunnel up -d 2>&1
    Write-Log ($out | Out-String).Trim()
} finally { Pop-Location }

Start-Sleep -Seconds 20
$running = @(& docker ps --format '{{.Names}}' 2>$null)
$missing = @($expected | Where-Object { $running -notcontains $_ })
if ($missing.Count -eq 0) {
    Write-Log 'Бүх контейнер сэргэв.'
} else {
    Write-Log ("АНХААР: дараах контейнер сэргээгүй: {0}" -f ($missing -join ', '))
    exit 1
}
