# Колонк — өгөгдлийн санг ЦЭВЭРЛЭЖ шинээр seed хийнэ (Docker prod stack).
#
#   .\reset-db.bat            # цэвэр суулгалт: данс, тохиргоо, эрх + admin/000000
#   .\reset-db.bat -Demo      # жишээ салбар, түлш, сав, бараа, хэрэглэгчидтэй
#
# Хийх зүйлс:
#   1. backups\before-reset-<огноо>.dump — бүрэн pg_dump (сэргээх боломжтой)
#   2. api-prod, worker зогсооно; public схемийг устгаж дахин үүсгэнэ
#   3. api-prod асаана (alembic upgrade head — бүх migration)
#   4. python -m app.seed [--demo]
#   5. ээлжийн зургийн хавтас, Redis дарааллыг цэвэрлэнэ; worker асаана
#
# БУЦААГДАХГҮЙ үйлдэл тул RESET гэж бичиж баталгаажуулна (-Force бол асуухгүй).
param(
    [switch]$Demo,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red; exit 1 }

$running = cmd /c "docker compose ps --status running db --format ""{{.Names}}"" 2>nul"
if (-not "$running".Trim()) { Fail "Docker db контейнер ажиллахгүй байна — эхлээд .\deploy.bat ажиллуулна уу" }

if (-not $Force) {
    Write-Host ""
    Write-Host "  АНХААР: одоогийн бүх өгөгдөл (ээлж, борлуулалт, журнал, харилцагч, салбар, хэрэглэгч) устна." -ForegroundColor Yellow
    if ($Demo) { Write-Host "  Дараа нь ЖИШЭЭ өгөгдлөөр (demo) seed хийнэ." -ForegroundColor Yellow }
    else       { Write-Host "  Дараа нь ЦЭВЭР seed хийнэ: зөвхөн данс, тохиргоо, эрх, admin/000000." -ForegroundColor Yellow }
    $answer = Read-Host "  Үргэлжлүүлэх бол RESET гэж бичнэ үү"
    if ($answer -ne "RESET") { Write-Host "  Цуцлав."; exit 0 }
}

# ── 1. Нөөцлөлт ───────────────────────────────────────────────────────────
Step "Нөөцлөлт авч байна"
if (-not (Test-Path "backups")) { New-Item -ItemType Directory "backups" | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dump  = Join-Path $PSScriptRoot "backups\before-reset-$stamp.dump"
# PS-ийн `>` binary гаралтыг гэмтээдэг тул cmd-ийн redirect ашиглана.
cmd /c "docker compose exec -T db pg_dump -Fc -U kolonk -d kolonk > ""$dump"" 2>nul"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dump) -or (Get-Item $dump).Length -eq 0) { Fail "pg_dump амжилтгүй" }
Ok "$dump ($([math]::Round((Get-Item $dump).Length / 1KB)) KB)"

# ── 2. Схем устгах ────────────────────────────────────────────────────────
Step "api-prod, worker зогсоож, схемийг устгаж байна"
cmd /c "docker compose stop api-prod worker >nul 2>&1"
cmd /c "docker compose exec -T db psql -U kolonk -d kolonk -c ""DROP SCHEMA public CASCADE; CREATE SCHEMA public;"" >nul 2>nul"
if ($LASTEXITCODE -ne 0) { Fail "Схем устгаж чадсангүй" }
Ok "public схем шинэ"

# ── 3. Migration ──────────────────────────────────────────────────────────
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

# ── 4. Seed ───────────────────────────────────────────────────────────────
Step ($(if ($Demo) { "Demo seed" } else { "Цэвэр seed" }))
$seedArgs = if ($Demo) { "--demo" } else { "" }
cmd /c "docker compose exec -T -e PYTHONIOENCODING=utf-8 api-prod python -m app.seed $seedArgs"
if ($LASTEXITCODE -ne 0) { Fail "Seed амжилтгүй" }

# ── 5. Хавсралт, Redis, worker ────────────────────────────────────────────
Step "Зургийн хавтас, Redis цэвэрлэж worker асааж байна"
cmd /c "docker compose exec -T api-prod sh -c ""rm -rf /code/uploads/shift_photos/*"" >nul 2>&1"
cmd /c "docker compose exec -T redis redis-cli FLUSHALL >nul 2>&1"
cmd /c "docker compose --profile prod up -d worker >nul 2>&1"
Ok "Бэлэн — http://localhost (admin / ПИН 000000, нэвтэрмэгц солино уу)"
