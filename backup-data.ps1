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
#   -Local switch өгвөл docker ажиллаж байсан ч локал 5434-өөс авна.
#
# Хоёр файлыг USB/cloud-оор шинэ PC-ийн repo root-д хуулаад
# тэнд .\restore-data.ps1 ажиллуулна. (Файлууд git-д ОРОХГҮЙ.)

param([switch]$Local)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red }

$dumpPath = Join-Path $PSScriptRoot "kolonk.dump"

# ── 1. Эх сангаа олох ──────────────────────────────────────────────────────
# PS 5.1-д docker-ын stderr ErrorRecord болдог тул cmd-ээр дамжуулна.
$running = cmd /c "docker compose ps --status running db --format ""{{.Names}}"" 2>nul"
$dockerDb = (-not $Local) -and [bool]"$running".Trim()

if ($dockerDb) {
    Step "Docker db контейнерээс dump хийж байна"
    # PS-ийн `>` нь binary гаралтыг гэмтээдэг тул cmd-ийн redirect ашиглана.
    cmd /c "docker compose exec -T db pg_dump -Fc -U kolonk -d kolonk > ""$dumpPath"" 2>nul"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dumpPath) -or (Get-Item $dumpPath).Length -eq 0) {
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
        # pg_dump кирилл замыг ойлгодоггүй тул түр (ASCII) зам руу бичээд зөөнө.
        $tmpDump = Join-Path $env:TEMP "kolonk-transfer.dump"
        if (Test-Path $tmpDump) { Remove-Item $tmpDump -Force }
        $env:PGPASSWORD = $dbPass
        cmd /c "`"$pgDump`" -Fc -h $dbHost -p $dbPort -U $dbUser -d $dbName -f `"$tmpDump`" 2>&1"
        $dumpOk = ($LASTEXITCODE -eq 0)
        Remove-Item Env:\PGPASSWORD
        if (-not $dumpOk -or -not (Test-Path $tmpDump)) { Fail "pg_dump амжилтгүй"; exit 1 }
        Move-Item $tmpDump $dumpPath -Force
    } else {
        # Локал pg_dump байхгүй бол түр контейнерээр хийнэ (host.docker.internal).
        # cmd-ийн redirect — PowerShell-ийн `>` binary файлыг гэмтээдэг.
        Step "Локал pg_dump олдсонгүй — Docker-ын pg_dump ашиглана"
        cmd /c "docker run --rm -e PGPASSWORD=$dbPass postgres:17-alpine pg_dump -Fc -h host.docker.internal -p $dbPort -U $dbUser -d $dbName > ""$dumpPath"" 2>nul"
        if ($LASTEXITCODE -ne 0 -or (Get-Item $dumpPath).Length -eq 0) { Fail "Dump амжилтгүй"; exit 1 }
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
    cmd /c "docker compose cp api-prod:/code/uploads ""$tmp"" 2>nul"
    if ((Test-Path $tmp) -and (Get-ChildItem $tmp -Recurse -File | Select-Object -First 1)) {
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
