# Колонк — өгөгдөл зөөвөрлөх багц үүсгэнэ (өөр PC руу нүүлгэхэд).
#
#   .\backup-data.ps1
#
# Үр дүн (repo root-д):
#   kolonk.dump         — өгөгдлийн сангийн бүрэн dump (pg_dump -Fc)
#   kolonk-uploads.zip  — ээлжийн зураг зэрэг хавсралтууд (байвал)
#
# Эх сангаа автоматаар олно:
#   1) Docker db контейнер ажиллаж байвал → түүнээс
#   2) Үгүй бол локал Postgres (127.0.0.1:5434, хөгжүүлэлтийн сан)
#
# Хоёр файлыг USB/cloud-оор шинэ PC-ийн repo root-д хуулаад
# тэнд .\restore-data.ps1 ажиллуулна. (Файлууд git-д ОРОХГҮЙ.)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red }

$dumpPath = Join-Path $PSScriptRoot "kolonk.dump"

# ── 1. Эх сангаа олох ──────────────────────────────────────────────────────
$dockerDb = $false
$null = docker compose ps --status running db --format "{{.Names}}" 2>$null
if ($? ) {
    $running = docker compose ps --status running db --format "{{.Names}}" 2>$null
    if ("$running".Trim()) { $dockerDb = $true }
}

if ($dockerDb) {
    Step "Docker db контейнерээс dump хийж байна"
    docker compose exec -T db pg_dump -Fc -U kolonk -d kolonk > $dumpPath
    if (-not $? -or -not (Test-Path $dumpPath) -or (Get-Item $dumpPath).Length -eq 0) {
        Fail "Dump амжилтгүй"; exit 1
    }
} else {
    Step "Локал Postgres (127.0.0.1:5434)-оос dump хийж байна"
    # backend/.env-ээс нууц үгийг уншина.
    $envLine = (Get-Content "backend\.env") -match "^DATABASE_URL=" | Select-Object -First 1
    if ($envLine -notmatch "postgresql\+asyncpg://([^:]+):([^@]+)@([^:/]+):(\d+)/(\w+)") {
        Fail "backend\.env доторх DATABASE_URL-ыг таньж чадсангүй"; exit 1
    }
    $dbUser = $Matches[1]; $dbPass = $Matches[2]
    $dbHost = $Matches[3]; $dbPort = $Matches[4]; $dbName = $Matches[5]

    $pgDump = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
    if (Test-Path $pgDump) {
        $env:PGPASSWORD = $dbPass
        & $pgDump -Fc -h $dbHost -p $dbPort -U $dbUser -d $dbName -f $dumpPath
        $dumpOk = $?
        Remove-Item Env:\PGPASSWORD
        if (-not $dumpOk) { Fail "pg_dump амжилтгүй"; exit 1 }
    } else {
        # Локал pg_dump байхгүй бол түр контейнерээр хийнэ (host.docker.internal).
        Step "Локал pg_dump олдсонгүй — Docker-ын pg_dump ашиглана"
        docker run --rm -e PGPASSWORD=$dbPass postgres:17-alpine `
            pg_dump -Fc -h host.docker.internal -p $dbPort -U $dbUser -d $dbName > $dumpPath
        if (-not $? -or (Get-Item $dumpPath).Length -eq 0) { Fail "Dump амжилтгүй"; exit 1 }
    }
}
$size = [math]::Round((Get-Item $dumpPath).Length / 1MB, 2)
Ok "kolonk.dump бэлэн ($size MB)"

# ── 2. Хавсралтын зургууд ──────────────────────────────────────────────────
$zipPath = Join-Path $PSScriptRoot "kolonk-uploads.zip"
$uploadsCollected = $false

if ($dockerDb) {
    # Prod volume-оос түр хавтас руу гаргаж авна.
    $tmp = Join-Path $env:TEMP "kolonk-uploads-export"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    docker compose cp api-prod:/code/uploads $tmp 2>$null
    if ($? -and (Test-Path $tmp) -and (Get-ChildItem $tmp -Recurse -File | Select-Object -First 1)) {
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path "$tmp\*" -DestinationPath $zipPath
        Remove-Item $tmp -Recurse -Force
        $uploadsCollected = $true
    }
}
if (-not $uploadsCollected -and (Test-Path "backend\uploads") -and
    (Get-ChildItem "backend\uploads" -Recurse -File | Select-Object -First 1)) {
    Step "backend\uploads-ыг архивлаж байна"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path "backend\uploads\*" -DestinationPath $zipPath
    $uploadsCollected = $true
}
if ($uploadsCollected) {
    Ok "kolonk-uploads.zip бэлэн"
} else {
    Ok "Хавсралтын зураг олдсонгүй — zip алгасав"
}

Write-Host ""
Write-Host "Зөөх файлууд:" -ForegroundColor Green
Write-Host "  kolonk.dump" -ForegroundColor Green
if ($uploadsCollected) { Write-Host "  kolonk-uploads.zip" -ForegroundColor Green }
Write-Host "Шинэ PC дээр repo root-д хуулаад:  .\restore-data.ps1" -ForegroundColor DarkGray
