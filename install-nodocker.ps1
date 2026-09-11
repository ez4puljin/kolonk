<#
.SYNOPSIS
    Колонк POS — Docker ДЭМЖДЭГГҮЙ компьютерт суулгах скрипт.

.DESCRIPTION
    install-nodocker.bat энэ скриптийг дууддаг.  Дараах дарааллаар бэлтгэнэ:

      1. winget-ээр шаардлагатай програмуудыг суулгана:
         Python 3.12, Node.js LTS, PostgreSQL 17, cloudflared, Memurai (Redis).
      2. backend\.env файлыг локал тохиргоотой үүсгэнэ (байхгүй бол).
      3. Компьютер асах бүрд систем өөрөө асдаг болгоно (register-startup.ps1).
      4. Хүсвэл шууд ажиллуулж үзнэ (startup.bat).

    Дараа нь систем startup.bat / start-dev.ps1-ээр Docker-гүйгээр ажиллана:
    PostgreSQL нь 5434 порт дээр тусдаа дата хавтастай, API нь 8000,
    POS нь 5173 порт дээр асна.

.NOTES
    Админ эрх шаардана — байхгүй бол өөрөө өргөгдөнө (UAC цонх гарна).
#>

$ErrorActionPreference = "Continue"

# ── Админ эрх ──────────────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Админ эрх шаардлагатай — UAC цонхоор зөвшөөрнө үү..." -ForegroundColor Yellow
    Start-Process powershell.exe `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit 0
}

$Root = $PSScriptRoot
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# ── 0. winget шалгах ───────────────────────────────────────────────────────
Write-Step "winget шалгаж байна"
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-Host @"
    winget олдсонгүй!

    Windows 10 дээр Microsoft Store-оос "App Installer"-ийг суулгана уу:
    https://apps.microsoft.com/detail/9NBLGGH4NNS1

    Дараа нь энэ скриптийг дахин ажиллуулна уу.
"@ -ForegroundColor Red
    Read-Host "Enter дарж гарна уу"
    exit 1
}
Write-Ok "Бэлэн"

# ── 1. Шаардлагатай програмууд ────────────────────────────────────────────
# (id, нэр, заавал эсэх, суусныг таних зам/команд)
$packages = @(
    @{ Id = "Python.Python.3.12";     Name = "Python 3.12";   Required = $true
       Check = { (Get-Command py -ErrorAction SilentlyContinue) -and ((py -3.12 -c "print(1)" 2>$null) -eq "1") } }
    @{ Id = "OpenJS.NodeJS.LTS";      Name = "Node.js LTS";   Required = $true
       Check = { Get-Command node -ErrorAction SilentlyContinue } }
    @{ Id = "PostgreSQL.PostgreSQL.17"; Name = "PostgreSQL 17"; Required = $true
       Check = { Test-Path "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" } }
    @{ Id = "Cloudflare.cloudflared"; Name = "cloudflared";   Required = $false
       Check = { Get-Command cloudflared -ErrorAction SilentlyContinue } }
    @{ Id = "Memurai.MemuraiDeveloper"; Name = "Memurai (Redis)"; Required = $false
       Check = { Get-Service Memurai -ErrorAction SilentlyContinue } }
)

foreach ($pkg in $packages) {
    Write-Step "$($pkg.Name)"
    if (& $pkg.Check) { Write-Ok "Аль хэдийн суусан"; continue }

    winget install --id $pkg.Id -e --silent `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Суулаа"
    } elseif ($pkg.Required) {
        Write-Host "    СУУСАНГҮЙ (winget код $LASTEXITCODE) — гараар суулгаад дахин ажиллуулна уу." -ForegroundColor Red
        Read-Host "Enter дарж гарна уу"
        exit 1
    } else {
        Write-Warn "Суусангүй (заавал биш). Гараар суулгаж болно:"
        if ($pkg.Id -like "Memurai*") {
            Write-Warn "  https://www.memurai.com/get-memurai (Developer edition — үнэгүй)"
            Write-Warn "  Redis-гүй бол насосны телеметр, фон ажил (и-баримт г.м) ажиллахгүй."
        }
        if ($pkg.Id -like "Cloudflare*") {
            Write-Warn "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            Write-Warn "  Интернэтэд гаргах шаардлагагүй бол хэрэггүй. Заавар: TUNNEL-SETUP.md"
        }
    }
}

# PATH шинэчлэгдсэн байж болзошгүй тул одоогийн сесст нэмнэ.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path", "User")

# ── 2. backend\.env ────────────────────────────────────────────────────────
Write-Step "backend\.env тохиргоо"
$envPath = Join-Path $Root "backend\.env"
if (Test-Path $envPath) {
    Write-Ok "Аль хэдийн байна — өөрчлөхгүй"
} else {
    # start-dev.ps1-ийн асаадаг локал PostgreSQL (порт 5434)-тай таарна.
    $secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    $backupDir = Join-Path $env:LOCALAPPDATA "kolonk-backups"
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
    @"
DATABASE_URL=postgresql+asyncpg://kolonk:kolonk_dev_2026@127.0.0.1:5434/kolonk
REDIS_URL=redis://127.0.0.1:6379/0
JWT_SECRET=$secret
JWT_EXPIRE_HOURS=12
VAT_RATE=0.10
EBARIMT_MODE=stub
BACKUP_DIR=$backupDir
TZ=Asia/Ulaanbaatar
"@ | Out-File -FilePath $envPath -Encoding utf8
    Write-Ok "Үүсгэлээ: $envPath"
}

# ── 3. Автомат асаалт ──────────────────────────────────────────────────────
Write-Step "Компьютер асахад систем өөрөө асдаг болгож байна"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "register-startup.ps1")

# ── 4. Дуусгах ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Суулгалт дууслаа." -ForegroundColor Green
Write-Host ""
Write-Host "  Дараагийн алхам:" -ForegroundColor Cyan
Write-Host "   1. startup.bat дээр 2 дарж системийг асаана (анхны удаад" -ForegroundColor Gray
Write-Host "      Python сан, npm сан татах тул 5-10 минут болно)." -ForegroundColor Gray
Write-Host "   2. Интернэтэд гаргах бол TUNNEL-SETUP.md зааврыг дагана." -ForegroundColor Gray
Write-Host "   3. Компьютер асахад хэрэглэгч НЭВТЭРСЭН байх ёстой — цоожтой" -ForegroundColor Gray
Write-Host "      орхидог бол Sysinternals Autologon-оор автомат нэвтрэлт тохируулна." -ForegroundColor Gray
Write-Host ""
$run = Read-Host "Одоо шууд асаах уу? (y/n)"
if ($run -eq "y") {
    Start-Process -FilePath (Join-Path $Root "startup.bat") -WorkingDirectory $Root
} else {
    Read-Host "Enter дарж гарна уу"
}
