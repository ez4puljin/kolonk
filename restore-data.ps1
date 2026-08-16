# Колонк — backup-data.ps1-ийн багцыг ажиллаж буй prod stack руу буулгана.
#
#   .\restore-data.ps1
#
# Урьдчилсан нөхцөл:
#   * .\start-docker.ps1 -Prod ажиллаж дууссан (db + api-prod контейнер асаалттай)
#   * kolonk.dump энэ хавтсанд байгаа (kolonk-uploads.zip — сонголт)
#
# АНХААР: Одоогийн сан ДАРАГДАНА (--clean). Буцаах бол өмнө нь
# .\backup-data.ps1-ээр өөрийн хуулбараа авч байгаарай.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red }

# PS 5.1: native stderr-ыг ErrorRecord болгохоос сэргийлнэ (start-docker.ps1-тэй ижил).
function Invoke-Native([string]$commandLine) {
    & cmd /c "$commandLine 2>&1"
}

if (-not (Test-Path "kolonk.dump")) {
    Fail "kolonk.dump олдсонгүй — эхлээд хуучин PC дээр .\backup-data.ps1 ажиллуулж, файлыг энд хуулна уу."
    exit 1
}

$running = cmd /c "docker compose ps --status running db --format ""{{.Names}}"" 2>nul"
if (-not "$running".Trim()) {
    Fail "db контейнер ажиллахгүй байна — эхлээд .\start-docker.ps1 -Prod ажиллуулна уу."
    exit 1
}

# ── 1. Өгөгдлийн сан ───────────────────────────────────────────────────────
Step "Dump-ыг контейнер руу хуулж байна"
Invoke-Native "docker compose cp kolonk.dump db:/tmp/kolonk.dump"
if ($LASTEXITCODE -ne 0) { Fail "Хуулж чадсангүй"; exit 1 }

Step "Сэргээж байна (одоогийн сан дарагдана)"
# --clean --if-exists: байгаа объектуудыг унагаад шинээр үүсгэнэ.
# Хуучин/шинэ схемийн зөрүүтэй үед зарим DROP анхааруулга хэвийн тул
# exit code-ыг өөрөө шалгахын оронд төгсгөлд нь баталгаажуулна.
Invoke-Native "docker compose exec -T db pg_restore --clean --if-exists --no-owner -U kolonk -d kolonk /tmp/kolonk.dump"
Invoke-Native "docker compose exec -T db rm -f /tmp/kolonk.dump"

$userCount = cmd /c 'docker compose exec -T db psql -U kolonk -d kolonk -tAc "SELECT count(*) FROM users" 2>nul'
$userCount = "$userCount".Trim()
if (-not $userCount -or $userCount -eq "0") {
    Fail "Сэргээлт амжилтгүй бололтой — users хүснэгт хоосон байна."
    exit 1
}
Ok "Сан сэргэлээ ($userCount хэрэглэгч)"

# ── 2. Хавсралтын зургууд (байвал) ────────────────────────────────────────
if (Test-Path "kolonk-uploads.zip") {
    Step "Хавсралтуудыг буулгаж байна"
    $tmp = Join-Path $env:TEMP "kolonk-uploads-import"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path "kolonk-uploads.zip" -DestinationPath $tmp
    Invoke-Native "docker compose cp ""$tmp\."" api-prod:/code/uploads/"
    if ($LASTEXITCODE -eq 0) { Ok "Зургууд орлоо" } else { Fail "Зураг хуулахад алдаа гарлаа (үргэлжилнэ)" }
    Remove-Item $tmp -Recurse -Force
}

# ── 3. API дахин ачаалж, миграцын түвшинг баталгаажуулна ──────────────────
Step "api-prod дахин асааж байна"
Invoke-Native "docker compose --profile prod restart api-prod worker" | Out-Null
$deadline = (Get-Date).AddMinutes(2)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest "http://localhost/api/health" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $ready) { Fail "API хариу өгөхгүй байна — docker compose logs api-prod харна уу"; exit 1 }

Ok "Бэлэн — http://localhost дээр өгөгдөлтэйгөө ажиллаж байна"
