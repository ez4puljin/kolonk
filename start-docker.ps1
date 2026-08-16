# Колонк — Docker горимоор асаах.
#
# УРЬДЧИЛСАН НӨХЦӨЛ: BIOS дээр Intel VT-x идэвхтэй байх ёстой.
# (ASUS: Delete → F7 → Advanced → CPU Configuration →
#  Intel (VMX) Virtualization Technology → Enabled → F10)
#
#   .\start-docker.ps1            → dev горим (API 8000, frontend-ийг host дээр)
#   .\start-docker.ps1 -Prod      → prod горим (бүгд Nginx-ээр http://localhost)
#   .\start-docker.ps1 -Down      → зогсоох
#   .\start-docker.ps1 -Reset     → өгөгдлийн сангийн volume-ыг устгаж шинээр эхлэх

param(
    [switch]$Prod,
    [switch]$Down,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$profileName = if ($Prod) { "prod" } else { "dev" }

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red }

# ── 0. Урьдчилсан шалгалт ──────────────────────────────────────────────────
Step "Виртуалчлалын шалгалт"
$hv = (systeminfo | Select-String "Virtualization Enabled In Firmware") -replace '.*:\s*', ''
if ($hv -match "No") {
    Fail "BIOS дээр виртуалчлал (Intel VT-x) унтраалттай байна."
    Write-Host ""
    Write-Host "  Docker Desktop Linux контейнер ажиллуулахад VT-x зайлшгүй шаардлагатай." -ForegroundColor Yellow
    Write-Host "  ASUS ROG STRIX дээр:" -ForegroundColor Yellow
    Write-Host "    1. Дахин асаах үед Delete дарж BIOS-д орно" -ForegroundColor Yellow
    Write-Host "    2. F7 → Advanced Mode" -ForegroundColor Yellow
    Write-Host "    3. Advanced → CPU Configuration" -ForegroundColor Yellow
    Write-Host "    4. Intel (VMX) Virtualization Technology → Enabled" -ForegroundColor Yellow
    Write-Host "    5. F10 → хадгалж гарах" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Одоохондоо .\start-dev.ps1 (локал горим) ашиглана уу." -ForegroundColor Yellow
    exit 1
}
Ok "VT-x идэвхтэй"

if ($Down) {
    Step "Зогсоож байна"
    docker compose --profile dev --profile prod down
    Ok "Зогслоо"
    exit 0
}

# ── 0.5. .env — байхгүй бол автоматаар үүсгэнэ (шинэ PC) ──────────────────
if (-not (Test-Path ".env")) {
    Step ".env үүсгэж байна (.env.example-ээс, санамсаргүй нууцтай)"
    function New-Secret([int]$len) {
        # PowerShell 5.1-д ажиллана — үсэг/тооноос санамсаргүй тэмдэгт мөр.
        $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
        $bytes = New-Object byte[] $len
        $rng.GetBytes($bytes)
        (($bytes | ForEach-Object { $chars[$_ % $chars.Length] }) -join "")
    }
    $dbPass = New-Secret 24
    $jwtSecret = New-Secret 48
    $envBody = (Get-Content ".env.example" -Raw) `
        -replace "POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$dbPass" `
        -replace "DATABASE_URL=.*", "DATABASE_URL=postgresql+asyncpg://kolonk:$dbPass@db:5432/kolonk" `
        -replace "JWT_SECRET=.*", "JWT_SECRET=$jwtSecret"
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot ".env"), $envBody)
    Ok ".env бэлэн (нууцууд автоматаар үүсэв)"
}

# ── 1. Docker engine ───────────────────────────────────────────────────────
Step "Docker engine"
$null = docker info --format "{{.ServerVersion}}" 2>&1
if (-not $?) {
    Warn "Docker Desktop асаж байна..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 6
        $null = docker info --format "{{.ServerVersion}}" 2>&1
        if ($?) { break }
    }
}
$ver = docker info --format "{{.ServerVersion}}" 2>&1
if (-not $?) { Fail "Docker engine асаагүй байна: $ver"; exit 1 }
Ok "engine $ver"

if ($Reset) {
    Step "Volume устгаж байна"
    docker compose --profile dev --profile prod down -v
    Ok "Цэвэрлэлээ"
}

# ── 2. Контейнерууд ────────────────────────────────────────────────────────
Step "Контейнер асааж байна ($profileName)"
docker compose --profile $profileName up -d --build
if (-not $?) { Fail "docker compose амжилтгүй"; exit 1 }

# ── 3. API бэлэн болохыг хүлээх ────────────────────────────────────────────
$apiSvc = if ($Prod) { "api-prod" } else { "api" }
Step "API бэлэн болохыг хүлээж байна"
$url = if ($Prod) { "http://localhost/api/health" } else { "http://localhost:8000/api/health" }
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 4 }
}
if (-not $ready) {
    Fail "API хариу өгөхгүй байна. Лог:"
    docker compose --profile $profileName logs --tail 40 $apiSvc
    exit 1
}
Ok "API бэлэн"

# ── 4. Seed — зөвхөн ХООСОН өгөгдлийн санд ─────────────────────────────────
# Restore хийсэн (бодит) өгөгдөл дээр demo дата эргэж нэмэгдэхээс сэргийлнэ.
Step "Seed дата"
$userCount = docker compose --profile $profileName exec -T db `
    psql -U kolonk -d kolonk -tAc "SELECT count(*) FROM users" 2>$null
if (-not $? -or "$userCount".Trim() -eq "" -or "$userCount".Trim() -eq "0") {
    docker compose --profile $profileName exec -T $apiSvc python -m app.seed
    Ok "Seed орлоо (шинэ сан)"
} else {
    Ok "Өгөгдөл аль хэдийн байна ($("$userCount".Trim()) хэрэглэгч) — seed алгасав"
}

Write-Host ""
if ($Prod) {
    Write-Host "POS: http://localhost" -ForegroundColor Green
} else {
    Write-Host "API: http://localhost:8000/api/docs" -ForegroundColor Green
    Write-Host "Frontend-ийг host дээр асаана:  cd frontend; npm run dev" -ForegroundColor Green
}
Write-Host "Зогсоох: .\start-docker.ps1 -Down" -ForegroundColor DarkGray
