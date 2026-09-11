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

    $exe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $exe)) { Write-Log "ЗОГСЛОО: $exe олдсонгүй."; exit 1 }

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

# --- 2. Контейнерууд бүрэн эсэхийг шалгах --------------------------------
$expected = @('kolonk-db-1','kolonk-redis-1','kolonk-api-prod-1',
              'kolonk-worker-1','kolonk-nginx-1','kolonk-cloudflared-1')

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
