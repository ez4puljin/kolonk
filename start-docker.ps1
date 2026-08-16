# Колонк — Docker горимоор асаах.
#
# ШИНЭ PC ДЭЭР start-docker.bat-аар ажиллуулна — шинэ Windows-ийн PowerShell
# бодлого (ExecutionPolicy=Restricted) .ps1-г шууд ажиллуулахыг хориглодог тул
# ".\start-docker.ps1" гэвэл "running scripts is disabled" алдаа гарна.
#
# УРЬДЧИЛСАН НӨХЦӨЛ: Docker Desktop суусан, BIOS дээр Intel VT-x идэвхтэй.
# (ASUS: Delete → F7 → Advanced → CPU Configuration →
#  Intel (VMX) Virtualization Technology → Enabled → F10)
#
#   start-docker.bat            → dev горим (API 8000, frontend-ийг host дээр)
#   start-docker.bat -Prod      → prod горим (бүгд Nginx-ээр http://localhost)
#   start-docker.bat -Down      → зогсоох
#   start-docker.bat -Reset     → өгөгдлийн сангийн volume-ыг устгаж шинээр эхлэх
#   (PowerShell дотроос бол: .\start-docker.ps1 [-Prod|-Down|-Reset])

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

# PS 5.1: native командын stderr (docker compose-ын progress г.м.) ErrorRecord
# болж $ErrorActionPreference=Stop-той хамт скриптийг унагадаг тул cmd-ээр
# дамжуулж цэвэр текст болгоно. Exit code-ыг $LASTEXITCODE-оос шалгана.
function Invoke-Native([string]$commandLine) {
    & cmd /c "$commandLine 2>&1"
}

# ── 0. Урьдчилсан шалгалт ──────────────────────────────────────────────────
# systeminfo удаан бөгөөд Windows-ийн хэлнээс хамаардаг (Hyper-V асаалттай үед
# шаардлагатай мөр нь огт гардаггүй) тул CIM-ээр шалгана.
Step "Виртуалчлалын шалгалт"
$vtOn = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
if (-not $vtOn) {
    # Hypervisor хараахан ажиллаагүй — процессорын firmware төлөвөөс харна.
    $vtOn = [bool](Get-CimInstance Win32_Processor |
        Where-Object { $_.VirtualizationFirmwareEnabled } | Select-Object -First 1)
}
if (-not $vtOn) {
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
    Write-Host "  Одоохондоо startup.bat (локал dev горим) ашиглана уу." -ForegroundColor Yellow
    exit 1
}
Ok "VT-x идэвхтэй"

# ── 0.2. Docker Desktop суусан эсэх ────────────────────────────────────────
# Урьд нь суулгаагүй машин дээр Start-Process шууд дуудаад ойлгомжгүй алдаагаар
# унадаг байсан — эндээс эрт, тодорхой заавартайгаар шалгана.
Step "Docker Desktop шалгалт"
# Machine-wide болон per-user (админ эрхгүй суулгасан) байрлалууд; жинхэнэ
# байрлалыг registry-гээс мөн асууна (InstallLocation).
$dockerRoots = @(
    "$env:ProgramFiles\Docker\Docker",
    "$env:LOCALAPPDATA\Programs\DockerDesktop",
    "$env:LOCALAPPDATA\Programs\Docker\Docker",
    "$env:LOCALAPPDATA\Docker"
)
foreach ($rk in "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop",
               "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop") {
    $loc = (Get-ItemProperty $rk -ErrorAction SilentlyContinue).InstallLocation
    if ($loc) { $dockerRoots = @($loc) + $dockerRoots }
}
$desktopExe = $dockerRoots | ForEach-Object { Join-Path $_ "Docker Desktop.exe" } |
    Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    # Дөнгөж суулгасны дараа нээлттэй байсан терминалын PATH шинэчлэгдээгүй
    # байдаг — CLI-ийн мэдэгдэж буй байрлалыг энэ процесст гараар нэмнэ.
    foreach ($root in $dockerRoots) {
        $bin = Join-Path $root "resources\bin"
        if (Test-Path (Join-Path $bin "docker.exe")) {
            $env:PATH = "$bin;$env:PATH"
            break
        }
    }
}
$dockerCli = Get-Command docker -ErrorAction SilentlyContinue

if (-not $desktopExe -and -not $dockerCli) {
    Fail "Docker Desktop суулгаагүй байна."
    Write-Host ""
    Write-Host "  Энэ скрипт ажиллахад Docker Desktop зайлшгүй шаардлагатай:" -ForegroundColor Yellow
    Write-Host "    1. https://www.docker.com/products/docker-desktop/ -оос татаж суулгана" -ForegroundColor Yellow
    Write-Host "    2. Docker Desktop-ыг НЭГ УДАА гараар нээж, эхний тохиргоог" -ForegroundColor Yellow
    Write-Host "       (Accept, WSL2 шинэчлэлт) дуустал хүлээнэ" -ForegroundColor Yellow
    Write-Host "    3. Дараа нь энэ скриптийг дахин ажиллуулна" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Docker-гүйгээр ажиллуулах бол: startup.bat (локал dev горим)" -ForegroundColor Yellow
    exit 1
}
if (-not $dockerCli) {
    Fail "docker команд олдсонгүй. Терминалаа хааж, ШИНЭЭР нээгээд дахин оролдоно уу."
    exit 1
}
Ok "Docker Desktop олдлоо"

# ── 0.3. WSL2 — Docker-ын VM давхарга ──────────────────────────────────────
# Docker Desktop суусан ч WSL2 байхгүй бол engine хэзээ ч асахгүй бөгөөд
# Docker Desktop цонхондоо "Virtualization support not detected" гэсэн
# төөрөгдүүлсэн алдаа харуулдаг (админ эрхгүй суулгалт WSL-ээ идэвхжүүлж
# чаддаггүй). Hyper-V backend хэрэглэдэг машинд vmcompute үйлчилгээ байдаг
# тул тэр тохиолдолд алгасна.
Step "WSL2 шалгалт"
cmd /c "wsl --status >nul 2>&1"
if ($LASTEXITCODE -ne 0 -and -not (Get-Service vmcompute -ErrorAction SilentlyContinue)) {
    Fail "WSL2 суулгаагүй байна — Docker Desktop-д зайлшгүй шаардлагатай."
    Write-Host ""
    Write-Host "  Засах (нэг удаа, дараа нь хэрэггүй):" -ForegroundColor Yellow
    Write-Host "    1. Start цэснээс PowerShell-ийг «Run as Administrator»-оор нээнэ" -ForegroundColor Yellow
    Write-Host "    2. Дараах командыг ажиллуулна:" -ForegroundColor Yellow
    Write-Host "         wsl --install --no-distribution" -ForegroundColor Yellow
    Write-Host "       (Store хаалттай бол: wsl --install --no-distribution --web-download)" -ForegroundColor Yellow
    Write-Host "    3. Компьютерээ restart хийнэ" -ForegroundColor Yellow
    Write-Host "    4. Docker Desktop-ыг нээж, 'Engine running' болтол хүлээнэ" -ForegroundColor Yellow
    Write-Host "    5. Энэ скриптийг дахин ажиллуулна" -ForegroundColor Yellow
    exit 1
}
Ok "VM давхарга (WSL2/Hyper-V) бэлэн"

if ($Down) {
    Step "Зогсоож байна"
    Invoke-Native "docker compose --profile dev --profile prod down"
    Ok "Зогслоо"
    exit 0
}

# ── 0.5. .env — байхгүй бол автоматаар үүсгэнэ (шинэ PC) ──────────────────
if (-not (Test-Path ".env")) {
    if (-not (Test-Path ".env.example")) {
        Fail ".env.example олдсонгүй — repo бүрэн татагдсан эсэхийг шалгана уу (git clone дахин хийх)."
        exit 1
    }
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
$ver = cmd /c "docker info --format ""{{.ServerVersion}}"" 2>nul"
if (-not $ver -and $desktopExe) {
    Warn "Docker Desktop асаж байна..."
    Start-Process $desktopExe
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 6
        $ver = cmd /c "docker info --format ""{{.ServerVersion}}"" 2>nul"
        if ($ver) { break }
    }
}
if (-not $ver) {
    Fail "Docker engine асаагүй байна."
    Write-Host ""
    Write-Host "  Анх суулгасны дараа Docker Desktop эхний тохиргоогоо гараар дуусгах" -ForegroundColor Yellow
    Write-Host "  шаардлагатай: Docker Desktop цонхыг нээж Accept дарна, WSL2 шинэчлэлт" -ForegroundColor Yellow
    Write-Host "  асуувал зөвшөөрч, зүүн доод буланд 'Engine running' болтол хүлээнэ." -ForegroundColor Yellow
    Write-Host "  Дараа нь энэ скриптийг дахин ажиллуулна уу." -ForegroundColor Yellow
    exit 1
}
Ok "engine $ver"

if ($Reset) {
    Step "Volume устгаж байна"
    Invoke-Native "docker compose --profile dev --profile prod down -v"
    Ok "Цэвэрлэлээ"
}

# ── 2. Контейнерууд ────────────────────────────────────────────────────────
Step "Контейнер асааж байна ($profileName)"
Invoke-Native "docker compose --profile $profileName up -d --build"
if ($LASTEXITCODE -ne 0) { Fail "docker compose амжилтгүй"; exit 1 }

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
    Invoke-Native "docker compose --profile $profileName logs --tail 40 $apiSvc"
    exit 1
}
Ok "API бэлэн"

# ── 4. Seed — зөвхөн ХООСОН өгөгдлийн санд ─────────────────────────────────
# Restore хийсэн (бодит) өгөгдөл дээр demo дата эргэж нэмэгдэхээс сэргийлнэ.
Step "Seed дата"
$userCount = cmd /c "docker compose --profile $profileName exec -T db psql -U kolonk -d kolonk -tAc ""SELECT count(*) FROM users"" 2>nul"
if (-not "$userCount".Trim() -or "$userCount".Trim() -eq "0") {
    Invoke-Native "docker compose --profile $profileName exec -T $apiSvc python -m app.seed"
    if ($LASTEXITCODE -ne 0) { Fail "Seed амжилтгүй"; exit 1 }
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
