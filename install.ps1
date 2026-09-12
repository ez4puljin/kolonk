<#
.SYNOPSIS
    Колонк POS — шинэ компьютерт суулгах НЭГДСЭН скрипт (install.bat дууддаг).

.DESCRIPTION
    Эхэнд «Docker ашиглах уу?» гэж асууна (эсвэл -Docker / -NoDocker тугаар
    шууд заана). Сонголтоос хамаарч ХОЁР ӨӨР зам явна, нэг нь нөгөөгийнхөө
    юуг ч хийхгүй:

      Docker горим (production, санал болгодог):
        · VT-x, Docker Desktop, WSL2 шалгана (байхгүй бол юу хийхийг зааж зогсоно)
        · 80 / 8000 / 5433 / 6380 портыг өөр програм эзэлсэн эсэхийг шалгаж,
          эзэмшигчийг нь нэрлэнэ (2026-09 сард Windows-ийн PostgreSQL 5433-ыг
          эзэлснээс db контейнер асаж чадахгүй, сайт нэг өдөр унасан)
        · .env үүсгэнэ (санамсаргүй нууцтай), хүсвэл Cloudflare Tunnel токен
        · watchdog бүртгэнэ — Docker унтарвал 5 минут тутам өөрөө сэргээнэ
        · start-docker.ps1 -Prod ажиллуулна (build → миграц → seed)
        · Python, Node, PostgreSQL, Memurai — ЮУ Ч СУУЛГАХГҮЙ

      Docker-гүй горим (Docker дэмждэггүй / хуучин PC):
        · winget-ээр Python 3.12, Node LTS, PostgreSQL (17 эсвэл 18 аль
          хэдийн байвал түүнийг ашиглана), cloudflared, Memurai
        · backend\.env үүсгэнэ, автомат асаалт бүртгэнэ (register-startup.ps1)
        · хүсвэл cloudflared-ийг Windows үйлчилгээгээр суулгана
        · Docker Desktop, compose, watchdog — ЮУ Ч ХИЙХГҮЙ

.PARAMETER Docker
    Асуулгүйгээр Docker горимоор суулгана.
.PARAMETER NoDocker
    Асуулгүйгээр Docker-гүй горимоор суулгана.
.PARAMETER DryRun
    Зөвхөн шалгалт хийж, юу хийхээ хэвлэнэ — суулгахгүй, файл бичихгүй,
    ажил бүртгэхгүй. Шинэ компьютерт эхлээд үүгээр үзэхийг зөвлөнө.
.PARAMETER SkipStart
    Суулгалтын төгсгөлд системийг асаахгүй.

.EXAMPLE
    .\install.bat
    .\install.bat -DryRun
    .\install.bat -Docker
    .\install.bat -NoDocker -SkipStart
#>

[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$NoDocker,
    [switch]$DryRun,
    [switch]$SkipStart
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root
. (Join-Path $Root "pg-locate.ps1")

function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "    $m" -ForegroundColor Red }
function Plan($m) { if ($DryRun) { Write-Host "    [DryRun] $m" -ForegroundColor Magenta } }
function Bye($code) {
    if ($code -ne 0 -or $script:Elevated) { Read-Host "Enter дарж гарна уу" | Out-Null }
    exit $code
}

if ($Docker -and $NoDocker) { Fail "-Docker ба -NoDocker хоёуланг нь зэрэг заах боломжгүй."; Bye 1 }

# UTF-8 BOM-гүй бичих — docker compose болон python-dotenv BOM-той .env-ийг
# буруу уншдаг.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function New-Secret([int]$len) {
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".ToCharArray()
    -join (1..$len | ForEach-Object { $chars | Get-Random })
}

function Get-PortOwner([int]$Port) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $c) { return $null }
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($p) { $p.ProcessName + ".exe" } else { "PID $($c.OwningProcess)" }
    $svc = Get-CimInstance Win32_Service -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($svc) { $name += " — Windows үйлчилгээ '$($svc.Name)'" }
    return $name
}

function Ask-Tunnel {
    # Хоёр горимд ижил: токен асууж буцаана; хүсэхгүй бол $null.
    Write-Host ""
    Write-Host "  Системийг интернэтээр (гар утасны дата) ашиглах бол Cloudflare Tunnel" -ForegroundColor Gray
    Write-Host "  хэрэгтэй. Токен авах заавар: TUNNEL-SETUP.md → 1-р хэсэг." -ForegroundColor Gray
    $a = Read-Host "  Cloudflare Tunnel холбох уу? (y/N)"
    if ($a -ne "y" -and $a -ne "Y") { return $null }
    $tok = (Read-Host "  Токен (eyJ... гэж эхэлсэн урт мөр)").Trim()
    if (-not $tok.StartsWith("eyJ")) {
        Warn "Токен 'eyJ'-ээр эхлэх ёстой — алгаслаа. Дараа нь гараар нэмж болно (TUNNEL-SETUP.md)."
        return $null
    }
    return $tok
}

# ═══════════════════════════════════════════════════════════════════════════
#  ГОРИМ СОНГОХ
# ═══════════════════════════════════════════════════════════════════════════
if (-not $Docker -and -not $NoDocker) {
    Write-Host ""
    Write-Host "  Колонк POS — суулгалт" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1) Docker горим  — production-д санал болгоно. Docker Desktop суусан," -ForegroundColor Gray
    Write-Host "                     BIOS дээр VT-x идэвхтэй шинэ PC. Бүгд контейнерт." -ForegroundColor Gray
    Write-Host "  2) Docker-гүй    — Docker дэмждэггүй эсвэл хуучин PC. Python, Node," -ForegroundColor Gray
    Write-Host "                     PostgreSQL шууд Windows дээр суугаад ажиллана." -ForegroundColor Gray
    Write-Host ""
    $choice = Read-Host "  Docker ашиглах уу? (1 = тийм, 2 = үгүй)"
    switch ($choice) {
        "1" { $Docker = $true }
        "2" { $NoDocker = $true }
        default { Fail "1 эсвэл 2 гэж оруулна уу."; Bye 1 }
    }
}
if ($DryRun) { Warn "DryRun — зөвхөн шалгаж, юу хийхээ хэвлэнэ. Юу ч өөрчлөхгүй." }

# ═══════════════════════════════════════════════════════════════════════════
#  А. DOCKER ГОРИМ
# ═══════════════════════════════════════════════════════════════════════════
function Install-DockerMode {
    Write-Host ""
    Write-Host "  ── Docker горим ──────────────────────────────────────────" -ForegroundColor Cyan

    # ── А.1 VT-x ────────────────────────────────────────────────────────────
    Step "Виртуалчлал (VT-x)"
    $vtOn = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
    if (-not $vtOn) {
        $vtOn = [bool](Get-CimInstance Win32_Processor |
            Where-Object { $_.VirtualizationFirmwareEnabled } | Select-Object -First 1)
    }
    if (-not $vtOn) {
        Fail "BIOS дээр виртуалчлал (Intel VT-x / AMD SVM) унтраалттай байна."
        Warn "BIOS → Advanced → CPU Configuration → Virtualization Technology → Enabled."
        Warn "Асаах боломжгүй бол Docker-гүй горимоор суулгана: install.bat -NoDocker"
        return 1
    }
    Ok "идэвхтэй"

    # ── А.2 Docker Desktop ──────────────────────────────────────────────────
    # Machine-wide ба per-user (админ эрхгүй суулгасан) байрлалууд + registry.
    Step "Docker Desktop"
    $roots = @(
        "$env:ProgramFiles\Docker\Docker",
        "$env:LOCALAPPDATA\Programs\DockerDesktop",
        "$env:LOCALAPPDATA\Programs\Docker\Docker",
        "$env:LOCALAPPDATA\Docker"
    )
    foreach ($rk in "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop",
                   "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop") {
        $loc = (Get-ItemProperty $rk -ErrorAction SilentlyContinue).InstallLocation
        if ($loc) { $roots = @($loc) + $roots }
    }
    $exe = $roots | ForEach-Object { Join-Path $_ "Docker Desktop.exe" } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) {
        Fail "Docker Desktop суулгаагүй байна."
        Warn "1. https://www.docker.com/products/docker-desktop/ -оос татаж суулгана"
        Warn "2. НЭГ УДАА гараар нээж, Accept / WSL2 шинэчлэлтийг дуустал хүлээнэ"
        Warn "3. Терминалаа хааж шинээр нээгээд install.bat -Docker дахин ажиллуулна"
        return 1
    }
    Ok $exe

    # ── А.3 WSL2 ────────────────────────────────────────────────────────────
    Step "WSL2 (Docker-ын VM давхарга)"
    cmd /c "wsl --status >nul 2>&1"
    if ($LASTEXITCODE -ne 0 -and -not (Get-Service vmcompute -ErrorAction SilentlyContinue)) {
        Fail "WSL2 суулгаагүй байна — Docker Desktop engine хэзээ ч асахгүй."
        Warn "Админ PowerShell:  wsl --install --no-distribution   → дараа нь restart."
        return 1
    }
    Ok "бэлэн"

    # ── А.4 Портын давхцал ──────────────────────────────────────────────────
    # docker-compose.yml хост дээр 80, 8000, 5433, 6380-ыг хатуу ашигладаг.
    Step "Портын давхцал (80, 8000, 5433, 6380)"
    $busy = @()
    foreach ($port in 80, 8000, 5433, 6380) {
        $owner = Get-PortOwner $port
        if ($owner) { $busy += "$port ← $owner"; Fail "$port : эзэлсэн — $owner" }
        else { Ok "$port : чөлөөтэй" }
    }
    if ($busy.Count -gt 0) {
        Write-Host ""
        Warn "Дээрх портуудыг чөлөөлөхгүй бол Docker-ын контейнер асахгүй."
        if ($busy -match "5433.*postgres") {
            # Сонсогч postgres.exe нь pg_ctl үйлчилгээний хүүхэд процесс тул PID-ээр
            # үйлчилгээ олдохгүй — нэрийг нь шууд үйлчилгээний жагсаалтаас авна.
            $pgSvcs = @(Get-Service postgresql* -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
            $svcName = if ($pgSvcs.Count -gt 0) { $pgSvcs -join ", " } else { "postgresql-x64-<хувилбар>" }
            Warn "5433-ыг Windows-ийн PostgreSQL үйлчилгээ ($svcName) эзэлж байна. Docker"
            Warn "горимд энэ үйлчилгээ ХЭРЭГГҮЙ. Хоёр сонголт (админ PowerShell):"
            Warn "  · Зогсоож, дахин асахгүй болгох:"
            foreach ($n in $pgSvcs) {
                Warn "      Stop-Service $n; Set-Service $n -StartupType Disabled"
            }
            if ($pgSvcs.Count -eq 0) { Warn "      Stop-Service $svcName; Set-Service $svcName -StartupType Disabled" }
            Warn "  · Эсвэл портыг нь солих: C:\Program Files\PostgreSQL\<хувилбар>\data\postgresql.conf"
            Warn "      port = 5435   → үйлчилгээг restart"
        }
        if ($busy -match "^80 ") { Warn "80-ыг IIS / Skype / өөр вэб сервер эзэлдэг — тухайн програмыг зогсооно." }
        if (-not $DryRun) { return 1 }
    }

    # ── А.5 .env ────────────────────────────────────────────────────────────
    Step ".env (Docker-ын тохиргоо, нууцууд)"
    $envPath = Join-Path $Root ".env"
    if (Test-Path $envPath) {
        Ok "аль хэдийн байна — өөрчлөхгүй"
    } elseif ($DryRun) {
        Plan ".env.example-ээс санамсаргүй нууцтай .env үүсгэнэ"
    } else {
        $example = Join-Path $Root ".env.example"
        if (-not (Test-Path $example)) { Fail ".env.example олдсонгүй — repo бүрэн татагдсан эсэхийг шалгана уу."; return 1 }
        $pw = New-Secret 24; $jwt = New-Secret 48
        $body = Get-Content $example -Raw
        $body = $body -replace "POSTGRES_PASSWORD=change_me", "POSTGRES_PASSWORD=$pw"
        $body = $body -replace ":change_me@", ":$pw@"
        $body = $body -replace "JWT_SECRET=change_me_long_random", "JWT_SECRET=$jwt"
        [System.IO.File]::WriteAllText($envPath, $body, $Utf8NoBom)
        Ok "үүсгэлээ (нууцууд санамсаргүй)"
    }

    # ── А.6 Cloudflare Tunnel (сонголт) ─────────────────────────────────────
    Step "Cloudflare Tunnel"
    $hasToken = (Test-Path $envPath) -and ((Get-Content $envPath) -match "^TUNNEL_TOKEN=eyJ")
    if ($hasToken) {
        Ok "токен .env-д аль хэдийн байна"
    } elseif ($DryRun) {
        Plan "Tunnel холбох эсэхийг асууж, токеныг .env-ийн TUNNEL_TOKEN-д бичнэ"
    } else {
        $tok = Ask-Tunnel
        if ($tok) {
            $lines = @(Get-Content $envPath)
            if ($lines -match "^TUNNEL_TOKEN=") { $lines = $lines -replace "^TUNNEL_TOKEN=.*", "TUNNEL_TOKEN=$tok" }
            else { $lines += "TUNNEL_TOKEN=$tok" }
            [System.IO.File]::WriteAllLines($envPath, $lines, $Utf8NoBom)
            Ok "токен .env-д бичигдлээ (compose-ын cloudflared сервис ашиглана)"
            Warn "Cloudflare дээр Public Hostname-ын URL-ыг nginx:80 гэж заана (TUNNEL-SETUP.md → 3)."
        } else {
            Ok "алгаслаа — дараа нь .env-д TUNNEL_TOKEN нэмээд deploy.bat ажиллуулна"
        }
    }

    # ── А.7 Watchdog ────────────────────────────────────────────────────────
    Step "Автомат сэргээлт (watchdog)"
    if ($DryRun) { Plan "Task Scheduler-т 'Kolonk POS - watchdog' бүртгэнэ (5 минут тутам)" }
    else {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "register-watchdog.ps1")
        if ($LASTEXITCODE -ne 0) { Warn "watchdog бүртгэгдсэнгүй — гараар: powershell -File register-watchdog.ps1" }
    }

    # ── А.8 Асаах ───────────────────────────────────────────────────────────
    Step "Систем асаах"
    if ($DryRun) { Plan "start-docker.ps1 -Prod  (build → миграц → seed → http://localhost)"; return 0 }
    if ($SkipStart) { Ok "алгаслаа (-SkipStart). Асаах: start-docker.bat -Prod"; return 0 }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "start-docker.ps1") -Prod
    if ($LASTEXITCODE -ne 0) { Fail "Асаалт амжилтгүй — дээрх мэдээллийг уншина уу."; return 1 }

    Write-Host ""
    Write-Host "  Суулгалт дууслаа (Docker горим)." -ForegroundColor Green
    Write-Host "   · Систем:        http://localhost   (анхны нэвтрэлт: admin / 000000 — ПИН-ээ солино уу)" -ForegroundColor Gray
    Write-Host "   · Шинэчлэлт:     git pull  →  deploy.bat" -ForegroundColor Gray
    Write-Host "   · Watchdog лог:  logs\watchdog.log" -ForegroundColor Gray
    Write-Host "   · Зогсоох:       start-docker.bat -Down" -ForegroundColor Gray
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════
#  Б. DOCKER-ГҮЙ ГОРИМ
# ═══════════════════════════════════════════════════════════════════════════
function Install-NativeMode {
    Write-Host ""
    Write-Host "  ── Docker-гүй горим ──────────────────────────────────────" -ForegroundColor Cyan

    # ── Б.1 Админ эрх (winget-ийн system суулгалт, cloudflared үйлчилгээ) ──
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin -and -not $DryRun) {
        Warn "Админ эрх шаардлагатай — UAC цонхоор зөвшөөрнө үү..."
        $fw = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoDocker"
        if ($SkipStart) { $fw += " -SkipStart" }
        Start-Process powershell.exe -ArgumentList $fw -Verb RunAs
        return 0
    }
    $script:Elevated = $isAdmin

    # ── Б.2 winget ──────────────────────────────────────────────────────────
    Step "winget"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "winget олдсонгүй. Microsoft Store-оос 'App Installer' суулгана:"
        Warn "https://apps.microsoft.com/detail/9NBLGGH4NNS1"
        return 1
    }
    Ok "бэлэн"

    # ── Б.3 Програмууд ──────────────────────────────────────────────────────
    # PostgreSQL: 17 эсвэл 18 аль хэдийн байвал ТҮҮНИЙГ ашиглана — хажууд нь
    # дахин суулгахгүй. Огт байхгүй бол 17 (Docker-ын dump-тай нийцтэй).
    $packages = @(
        @{ Id = "Python.Python.3.12";       Name = "Python 3.12";     Required = $true
           Check = { (Get-Command py -ErrorAction SilentlyContinue) -and ((py -3.12 -c "print(1)" 2>$null) -eq "1") } }
        @{ Id = "OpenJS.NodeJS.LTS";        Name = "Node.js LTS";     Required = $true
           Check = { Get-Command node -ErrorAction SilentlyContinue } }
        @{ Id = "PostgreSQL.PostgreSQL.17"; Name = "PostgreSQL";      Required = $true
           Check = { [bool](Find-PgBin) } }
        @{ Id = "Cloudflare.cloudflared";   Name = "cloudflared";     Required = $false
           Check = { Get-Command cloudflared -ErrorAction SilentlyContinue } }
        @{ Id = "Memurai.MemuraiDeveloper"; Name = "Memurai (Redis)"; Required = $false
           Check = { Get-Service Memurai -ErrorAction SilentlyContinue } }
    )
    foreach ($pkg in $packages) {
        Step $pkg.Name
        if (& $pkg.Check) {
            if ($pkg.Name -eq "PostgreSQL") { Ok "аль хэдийн суусан: $(Find-PgBin)" } else { Ok "аль хэдийн суусан" }
            continue
        }
        if ($DryRun) { Plan "winget install --id $($pkg.Id)"; continue }
        winget install --id $pkg.Id -e --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) { Ok "суулаа" }
        elseif ($pkg.Required) {
            Fail "СУУСАНГҮЙ (winget код $LASTEXITCODE) — гараар суулгаад дахин ажиллуулна уу."
            return 1
        } else {
            Warn "суусангүй (заавал биш)."
            if ($pkg.Id -like "Memurai*")    { Warn "  Redis-гүй бол фон ажил (и-баримт г.м) ажиллахгүй: https://www.memurai.com/get-memurai" }
            if ($pkg.Id -like "Cloudflare*") { Warn "  Интернэтэд гаргахгүй бол хэрэггүй. Заавар: TUNNEL-SETUP.md" }
        }
    }
    # Шинээр суусан програмуудын PATH энэ сесст орж ирээгүй байдаг.
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Find-PgBin) -and -not $DryRun) { Fail "PostgreSQL олдсонгүй (C:\Program Files\PostgreSQL\<17|18>\bin)."; return 1 }

    # ── Б.4 backend\.env ────────────────────────────────────────────────────
    Step "backend\.env"
    $envPath = Join-Path $Root "backend\.env"
    if (Test-Path $envPath) { Ok "аль хэдийн байна — өөрчлөхгүй" }
    elseif ($DryRun) { Plan "backend\.env үүсгэнэ (локал PostgreSQL 5434, санамсаргүй JWT нууц)" }
    else {
        $backupDir = Join-Path $env:LOCALAPPDATA "kolonk-backups"
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        # start-dev.ps1-ийн асаадаг тусдаа instance (порт 5434)-тай таарна.
        $body = @(
            "DATABASE_URL=postgresql+asyncpg://kolonk:kolonk_dev_2026@127.0.0.1:5434/kolonk",
            "REDIS_URL=redis://127.0.0.1:6379/0",
            "JWT_SECRET=$(New-Secret 48)",
            "JWT_EXPIRE_HOURS=12",
            "VAT_RATE=0.10",
            "EBARIMT_MODE=stub",
            "BACKUP_DIR=$backupDir",
            "TZ=Asia/Ulaanbaatar"
        )
        [System.IO.File]::WriteAllLines($envPath, $body, $Utf8NoBom)
        Ok "үүсгэлээ"
    }

    # ── Б.5 Cloudflare Tunnel (сонголт) — Windows үйлчилгээгээр ────────────
    Step "Cloudflare Tunnel"
    $cfSvc = Get-Service cloudflared -ErrorAction SilentlyContinue
    if ($cfSvc) { Ok "cloudflared үйлчилгээ аль хэдийн байна ($($cfSvc.Status))" }
    elseif ($DryRun) { Plan "Tunnel холбох эсэхийг асууж, 'cloudflared service install <токен>' ажиллуулна" }
    elseif (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { Warn "cloudflared байхгүй тул алгаслаа." }
    else {
        $tok = Ask-Tunnel
        if ($tok) {
            cloudflared service install $tok
            if ($LASTEXITCODE -eq 0) {
                Ok "үйлчилгээ суулаа — компьютер асах бүрд өөрөө асна"
                # Docker-гүй горимд Vite (5173) frontend-ийг үйлчилж, /api-г 8000 руу
                # өөрөө дамжуулдаг — 8000-ыг шууд заавал POS дэлгэц нээгдэхгүй.
                Warn "Cloudflare дээр Public Hostname-ын URL-ыг localhost:5173 гэж заана (TUNNEL-SETUP.md → 1.5)."
            } else { Fail "cloudflared service install амжилтгүй (код $LASTEXITCODE)." }
        } else { Ok "алгаслаа" }
    }

    # ── Б.6 Автомат асаалт ──────────────────────────────────────────────────
    Step "Автомат асаалт"
    if ($DryRun) { Plan "Task Scheduler-т 'Kolonk POS - autostart' бүртгэнэ (нэвтрэхэд start-dev.ps1)" }
    else {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "register-startup.ps1")
        if ($LASTEXITCODE -ne 0) { Warn "бүртгэгдсэнгүй — гараар: powershell -File register-startup.ps1" }
    }

    # ── Б.7 Асаах ───────────────────────────────────────────────────────────
    Step "Систем асаах"
    if ($DryRun) { Plan "startup.bat  (сан 5434 → API 8000 → POS 5173, браузер нээнэ)"; return 0 }
    Write-Host ""
    Write-Host "  Суулгалт дууслаа (Docker-гүй горим)." -ForegroundColor Green
    Write-Host "   · Асаах:      startup.bat   (эхний удаа Python/npm сан татах тул 5–10 мин)" -ForegroundColor Gray
    Write-Host "   · Зогсоох:    stop.bat" -ForegroundColor Gray
    Write-Host "   · Шинэчлэлт:  git pull → stop.bat → startup.bat" -ForegroundColor Gray
    Write-Host "   · Компьютер асахад хэрэглэгч НЭВТЭРСЭН байх ёстой (Autologon)." -ForegroundColor Gray
    if ($SkipStart) { return 0 }
    $run = Read-Host "  Одоо шууд асаах уу? (y/n)"
    if ($run -eq "y" -or $run -eq "Y") {
        Start-Process -FilePath (Join-Path $Root "startup.bat") -WorkingDirectory $Root
    }
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════
$script:Elevated = $false
if ($Docker) { $code = Install-DockerMode } else { $code = Install-NativeMode }
if ($null -eq $code) { $code = 0 }
Bye $code
