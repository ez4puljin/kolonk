# Колонк — өгөгдлийн санг ЦЭВЭРЛЭЖ шинээр seed хийнэ.
#
#   .\reset-db.bat              # цэвэр суулгалт: данс, тохиргоо, эрх + admin/000000
#   .\reset-db.bat -Demo        # жишээ салбар, түлш, сав, бараа, хэрэглэгчидтэй
#   .\reset-db.bat -NoDocker    # Docker-гүй суулгалт (локал PostgreSQL 5434 + backend\.venv)
#   .\reset-db.bat -Force       # RESET баталгаажуулалт асуухгүй
#
# Горимыг өөрөө таньдаг: Docker db контейнер ажиллаж байвал Docker, үгүй бол
# backend\.venv байвал NoDocker. -NoDocker өгвөл заавал локал горим.
#
# Хийх зүйлс (хоёр горимд ижил):
#   1. backups\before-reset-<огноо>.dump — бүрэн pg_dump (сэргээх боломжтой)
#   2. API, worker зогсооно; public схемийг устгаж дахин үүсгэнэ
#   3. Бүх migration (alembic upgrade head)
#   4. python -m app.seed [--demo]
#   5. ээлжийн зургийн хавтас, Redis дарааллыг цэвэрлэнэ; API, worker асаана
#
# БУЦААГДАХГҮЙ үйлдэл тул RESET гэж бичиж баталгаажуулна.
param(
    [switch]$Demo,
    [switch]$NoDocker,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red; exit 1 }

# ── Горим ─────────────────────────────────────────────────────────────────
$dockerDb = $false
if (-not $NoDocker) {
    # PS 5.1-д docker-ын stderr ErrorRecord болдог тул cmd-ээр дамжуулна.
    $running = cmd /c "docker compose ps --status running db --format ""{{.Names}}"" 2>nul"
    $dockerDb = [bool]"$running".Trim()
}
if (-not $dockerDb -and -not (Test-Path "backend\.venv\Scripts\python.exe")) {
    Fail "Docker db контейнер ч, backend\.venv ч олдсонгүй — эхлээд .\deploy.bat (Docker) эсвэл .\install.bat -NoDocker ажиллуулна уу"
}
$mode = if ($dockerDb) { "Docker" } else { "NoDocker (локал PostgreSQL)" }

if (-not $Force) {
    Write-Host ""
    Write-Host "  Горим: $mode" -ForegroundColor Yellow
    Write-Host "  АНХААР: одоогийн бүх өгөгдөл (ээлж, борлуулалт, журнал, харилцагч, салбар, хэрэглэгч) устна." -ForegroundColor Yellow
    if ($Demo) { Write-Host "  Дараа нь ЖИШЭЭ өгөгдлөөр (demo) seed хийнэ." -ForegroundColor Yellow }
    else       { Write-Host "  Дараа нь ЦЭВЭР seed хийнэ: зөвхөн данс, тохиргоо, эрх, admin/000000." -ForegroundColor Yellow }
    $answer = Read-Host "  Үргэлжлүүлэх бол RESET гэж бичнэ үү"
    if ($answer -ne "RESET") { Write-Host "  Цуцлав."; exit 0 }
}

if (-not (Test-Path "backups")) { New-Item -ItemType Directory "backups" | Out-Null }
$stamp    = Get-Date -Format "yyyyMMdd-HHmmss"
$dump     = Join-Path $PSScriptRoot "backups\before-reset-$stamp.dump"
$seedArgs = if ($Demo) { "--demo" } else { "" }

# ═══════════════════════════════════════════════════════════════════════════
if ($dockerDb) {
    # ── 1. Нөөцлөлт ─────────────────────────────────────────────────────
    Step "Нөөцлөлт авч байна (Docker db)"
    # PS-ийн `>` binary гаралтыг гэмтээдэг тул cmd-ийн redirect ашиглана.
    cmd /c "docker compose exec -T db pg_dump -Fc -U kolonk -d kolonk > ""$dump"" 2>nul"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dump) -or (Get-Item $dump).Length -eq 0) { Fail "pg_dump амжилтгүй" }
    Ok "$dump ($([math]::Round((Get-Item $dump).Length / 1KB)) KB)"

    # ── 2. Схем устгах ───────────────────────────────────────────────────
    Step "api-prod, worker зогсоож, схемийг устгаж байна"
    cmd /c "docker compose stop api-prod worker >nul 2>&1"
    cmd /c "docker compose exec -T db psql -U kolonk -d kolonk -c ""DROP SCHEMA public CASCADE; CREATE SCHEMA public;"" >nul 2>nul"
    if ($LASTEXITCODE -ne 0) { Fail "Схем устгаж чадсангүй" }
    Ok "public схем шинэ"

    # ── 3. Migration ─────────────────────────────────────────────────────
    Step "api-prod асааж migration ажиллуулж байна"
    cmd /c "docker compose --profile prod up -d api-prod >nul 2>&1"
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost/api/health" -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) { Fail "API асаагүй — docker compose logs api-prod харна уу" }
    $head = cmd /c "docker compose exec -T db psql -U kolonk -d kolonk -tAc ""select version_num from alembic_version"" 2>nul"
    Ok "migration head: $("$head".Trim())"

    # ── 4. Seed ──────────────────────────────────────────────────────────
    Step ($(if ($Demo) { "Demo seed" } else { "Цэвэр seed" }))
    cmd /c "docker compose exec -T -e PYTHONIOENCODING=utf-8 api-prod python -m app.seed $seedArgs"
    if ($LASTEXITCODE -ne 0) { Fail "Seed амжилтгүй" }

    # ── 5. Хавсралт, Redis, worker ───────────────────────────────────────
    Step "Зургийн хавтас, Redis цэвэрлэж worker асааж байна"
    cmd /c "docker compose exec -T api-prod sh -c ""rm -rf /code/uploads/shift_photos/*"" >nul 2>&1"
    cmd /c "docker compose exec -T redis redis-cli FLUSHALL >nul 2>&1"
    cmd /c "docker compose --profile prod up -d worker >nul 2>&1"
    Ok "Бэлэн — http://localhost (admin / ПИН 000000, нэвтэрмэгц солино уу)"
    exit 0
}

# ═══════════════════════════════════════════════════════════════════════════
# NoDocker: start-dev.ps1-тэй ижил локал PostgreSQL (5434), backend\.venv.
. (Join-Path $PSScriptRoot "pg-locate.ps1")
$PgBin  = Find-PgBin
if (-not $PgBin -or -not (Test-Path "$PgBin\pg_ctl.exe")) { Fail "PostgreSQL олдсонгүй (C:\Program Files\PostgreSQL\<17|18>\bin)" }
$Python = "$PSScriptRoot\backend\.venv\Scripts\python.exe"
$PgData = "$env:LOCALAPPDATA\kolonk-devdb"
$PgLog  = "$env:LOCALAPPDATA\kolonk-devdb.log"

# backend\.env-ээс холболтыг уншина (backup-data.ps1-тэй ижил).
$envLine = (Get-Content "backend\.env") -match "^DATABASE_URL=" | Select-Object -First 1
if ($envLine -notmatch "postgresql\+asyncpg://([^:]+):([^@]+)@([^:/]+):(\d+)/(\w+)") {
    Fail "backend\.env доторх DATABASE_URL-ыг таньж чадсангүй"
}
$dbUser = $Matches[1]; $dbPass = $Matches[2]
$dbHost = $Matches[3]; $dbPort = $Matches[4]; $dbName = $Matches[5]
$env:PGPASSWORD = $dbPass

function Invoke-Pg([string]$Exe, [string[]]$ArgList) {
    # Native програмууд stderr рүү мэдээлэл бичдэг тул cmd-ээр дамжуулж exit code-оор шүүнэ.
    $quoted = ($ArgList | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join " "
    cmd /c """$Exe"" $quoted 2>&1"
    return $LASTEXITCODE
}

# ── 1. Бүгдийг зогсоож, зөвхөн PostgreSQL асаах ─────────────────────────
Step "API, worker зогсоож байна"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start-dev.ps1") -Stop | Out-Null
if (-not (Get-NetTCPConnection -State Listen -LocalPort ([int]$dbPort) -ErrorAction SilentlyContinue)) {
    Step "PostgreSQL ($dbPort) асааж байна"
    $pgArgs = '-D "{0}" -l "{1}" -o "-p {2} -c listen_addresses=127.0.0.1" start' -f $PgData, $PgLog, $dbPort
    Start-Process -FilePath "$PgBin\pg_ctl.exe" -ArgumentList $pgArgs -WindowStyle Hidden
    $up = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        cmd /c """$PgBin\pg_isready.exe"" -h $dbHost -p $dbPort -U $dbUser >nul 2>&1"
        if ($LASTEXITCODE -eq 0) { $up = $true; break }
    }
    if (-not $up) { Fail "PostgreSQL хариу өгөхгүй байна ($PgLog)" }
}
Ok "PostgreSQL бэлэн"

# ── 2. Нөөцлөлт ──────────────────────────────────────────────────────────
Step "Нөөцлөлт авч байна"
# pg_dump кирилл замыг ойлгодоггүй тул TEMP-д бичээд зөөнө.
$tmpDump = Join-Path $env:TEMP "kolonk-before-reset.dump"
if (Test-Path $tmpDump) { Remove-Item $tmpDump -Force }
$rc = Invoke-Pg "$PgBin\pg_dump.exe" @("-Fc", "-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", $dbName, "-f", $tmpDump)
if ($rc -ne 0 -or -not (Test-Path $tmpDump)) { Fail "pg_dump амжилтгүй" }
Move-Item $tmpDump $dump -Force
Ok "$dump ($([math]::Round((Get-Item $dump).Length / 1KB)) KB)"

# ── 3. Схем устгах ───────────────────────────────────────────────────────
Step "public схемийг устгаж дахин үүсгэж байна"
$rc = Invoke-Pg "$PgBin\psql.exe" @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", $dbName, "-v", "ON_ERROR_STOP=1", "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
if ($rc -ne 0) { Fail "Схем устгаж чадсангүй" }
Ok "public схем шинэ"

# ── 4. Migration + seed ──────────────────────────────────────────────────
Step "Migration (alembic upgrade head)"
Push-Location "$PSScriptRoot\backend"
try {
    cmd /c """$Python"" -m alembic upgrade head 2>&1"
    if ($LASTEXITCODE -ne 0) { Fail "Migration амжилтгүй" }
    Step ($(if ($Demo) { "Demo seed" } else { "Цэвэр seed" }))
    $env:PYTHONIOENCODING = "utf-8"
    cmd /c """$Python"" -m app.seed $seedArgs 2>&1"
    if ($LASTEXITCODE -ne 0) { Fail "Seed амжилтгүй" }
} finally { Pop-Location }

# ── 5. Хавсралт, Redis ───────────────────────────────────────────────────
Step "Зургийн хавтас, Redis цэвэрлэж байна"
Remove-Item -Recurse -Force "$PSScriptRoot\backend\uploads\shift_photos" -ErrorAction SilentlyContinue
$redisCli = @("memurai-cli", "redis-cli") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if ($redisCli) { cmd /c "$redisCli FLUSHALL >nul 2>&1" } else { Write-Host "    (redis-cli/memurai-cli олдсонгүй — Redis дараалал алгасав)" -ForegroundColor DarkGray }

# ── 6. Асаах ─────────────────────────────────────────────────────────────
Step "API, worker асааж байна (start-dev.ps1)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start-dev.ps1")
Ok "Бэлэн — admin / ПИН 000000, нэвтэрмэгц солино уу"
