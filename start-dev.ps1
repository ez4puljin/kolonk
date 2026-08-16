# Колонк — локал хөгжүүлэлтийн орчин асаах (Docker шаардахгүй).
#
#   .\start-dev.ps1                 → сан + API + worker + frontend асаана
#   .\start-dev.ps1 -Seed           → нэмээд seed дата суулгана
#   .\start-dev.ps1 -Open           → бэлэн болмогц браузер нээнэ
#   .\start-dev.ps1 -Quiet          → далд горим (лог нь logs\ хавтсанд)
#   .\start-dev.ps1 -Stop           → бүгдийг зогсооно
#
# startup.bat нь үүнийг -Seed -Open -Quiet-тэйгээр дуудна.

param(
    [switch]$Seed,
    [switch]$Stop,
    [switch]$Open,     # бэлэн болмогц браузер нээх
    [switch]$Quiet     # процессуудыг далд ажиллуулж, логийг файлд бичих
)

# Native програмууд (alembic, initdb, psql) мэдээллээ stderr рүү бичдэг.
# PowerShell 5.1-д ErrorActionPreference="Stop" үед энэ нь NativeCommandError
# болж скриптийг зогсоодог тул "Continue" болгож, гарцын кодыг өөрсдөө шалгана.
$ErrorActionPreference = "Continue"
$Root     = $PSScriptRoot
$PgBin    = "C:\Program Files\PostgreSQL\17\bin"
$PgData   = "$env:LOCALAPPDATA\kolonk-devdb"
$PgLog    = "$env:LOCALAPPDATA\kolonk-devdb.log"
$PgPort   = 5434
$Python   = "$Root\backend\.venv\Scripts\python.exe"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

$LogDir = "$Root\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# Фон процесс асаана. -Quiet үед цонхгүй, лог нь logs\<нэр>.log руу бичигдэнэ.
# $Args гэж нэрлэж БОЛОХГҮЙ — PowerShell-ийн хамгаалагдсан автомат хувьсагч.
function Start-Bg {
    param([string]$Exe, [string[]]$ArgList, [string]$Cwd, [string]$Name)
    $p = @{ FilePath = $Exe; ArgumentList = $ArgList; WorkingDirectory = $Cwd }
    if ($Quiet) {
        $p.WindowStyle             = "Hidden"
        $p.RedirectStandardOutput  = "$LogDir\$Name.log"
        $p.RedirectStandardError   = "$LogDir\$Name.err"
    }
    Start-Process @p
}

function Invoke-Native {
    param([string]$Exe, [string[]]$ArgList, [string]$What)
    # Гарцыг хадгална — алдаа гарвал шалтгааныг нь шууд харуулна.
    # Зөвхөн "амжилтгүй (код 1)" гэж бичих нь юу болсныг мэдэгдэхгүй.
    $output = & $Exe @ArgList 2>&1 | ForEach-Object { $_.ToString() }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    $What амжилтгүй (код $LASTEXITCODE)" -ForegroundColor Red
        $output | Select-Object -Last 15 | ForEach-Object {
            Write-Host "      $_" -ForegroundColor DarkGray
        }
        exit 1
    }
}

# PostgreSQL холболт хүлээж авахад бэлэн болохыг хүлээнэ.
#
# ЧУХАЛ: порт нээгдсэн нь бэлэн гэсэн үг БИШ. Сервер сокетоо эрт нээчихээд
# сэргээлт (recovery) дуустал "the database system is starting up" гэж
# татгалзаж байдаг — цэвэр бус унтарсны дараа энэ нь хэдэн секунд үргэлжилнэ.
# Тиймээс pg_isready-гээр жинхэнэ бэлэн байдлыг шалгана.
function Wait-Postgres {
    param([int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        & "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $PgPort -q
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

# Тухайн порт дээр сонсож буй процессыг зогсооно.
# node.exe нь "C:\Program Files\nodejs\"-д байрладаг тул замаар шүүх нь Vite-д
# ажиллахгүй — иймд портоор нь тодорхойлно.
function Stop-Port {
    param([int]$Port)
    $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    # $pid нь PowerShell-ийн зөвхөн уншигдах автомат хувьсагч тул өөр нэр авна
    foreach ($procId in ($conns.OwningProcess | Sort-Object -Unique)) {
        if ($procId -and $procId -ne 0) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

# Процессын бүх удам сангийн жагсаалт (гүн хайлт).
function Get-Descendants {
    param([int]$ProcessId)
    $kids = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($k in $kids) {
        $k.ProcessId
        Get-Descendants $k.ProcessId
    }
}

# Командын мөрөөр язгуур процессыг олж, УДАМ САНГИЙН ХАМТ зогсооно.
#
# Яагаад мод бүхэлд нь: uvicorn --reload нь серверийг тусдаа дэд процессоор
# ажиллуулдаг ба тэр нь сонсож буй сокетыг өвлөн авдаг. Уг дэд процессын
# командын мөр нь "multiprocessing.spawn ..." байдаг тул "uvicorn" гэж хайхад
# олдохгүй, бас венвийн бус python-оор ажилладаг тул замаар ч олдохгүй.
# Түүнийг үлдээвэл 8000 порт чөлөөлөгдөхгүй.
#
# Дараалал чухал: эхлээд ЯЗГУУРыг алж reload дахин асаахыг зогсоогоод,
# дараа нь өнчирсөн үр удмыг цэвэрлэнэ.
function Stop-Tree {
    param([string]$Exe, [string]$Pattern)
    $roots = Get-CimInstance Win32_Process -Filter "Name='$Exe'" -ErrorAction SilentlyContinue |
             Where-Object { $_.CommandLine -like $Pattern }
    foreach ($r in $roots) {
        $kids = @(Get-Descendants $r.ProcessId)
        Stop-Process -Id $r.ProcessId -Force -ErrorAction SilentlyContinue
        foreach ($k in $kids) { Stop-Process -Id $k -Force -ErrorAction SilentlyContinue }
    }
}

if ($Stop) {
    Write-Step "Зогсоож байна"
    Stop-Tree "python.exe" "*uvicorn*app.main:app*"      # API (reload эцэг + сервер хүүхэд)
    Stop-Tree "python.exe" "*arq*app.worker*"            # ARQ worker
    Stop-Tree "node.exe"   "*vite*"                      # Vite dev server
    Stop-Port 8000          # үлдсэн сонсогч байвал
    Stop-Port 5173
    # энэ төслийн венвийн бусад python (жишээ нь гараар асаасан)
    Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$Root*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath "$PgBin\pg_ctl.exe" `
        -ArgumentList ('-D "{0}" stop -m fast' -f $PgData) -Wait -NoNewWindow
    Start-Sleep -Seconds 1
    $left = @(8000, 5173, $PgPort) | Where-Object {
        Get-NetTCPConnection -State Listen -LocalPort $_ -ErrorAction SilentlyContinue
    }
    if ($left) { Write-Warn ("Зогсоогүй порт: " + ($left -join ", ")) }
    else { Write-Ok "Бүгд зогслоо" }
    exit 0
}

# ── 1. PostgreSQL ──────────────────────────────────────────────────────────
Write-Step "PostgreSQL ($PgPort)"
if (-not (Test-Path $PgBin)) {
    Write-Warn "PostgreSQL 17 олдсонгүй: $PgBin"
    exit 1
}
if (-not (Test-Path $PgData)) {
    Write-Ok "Шинэ өгөгдлийн сангийн хавтас үүсгэж байна..."
    $pwfile = "$env:TEMP\kolonk_pw.txt"
    "kolonk_dev_2026" | Out-File -FilePath $pwfile -Encoding ascii -NoNewline
    & "$PgBin\initdb.exe" -D $PgData -U kolonk --auth-local=trust --auth-host=scram-sha-256 --pwfile=$pwfile -E UTF8 | Out-Null
    Remove-Item $pwfile -Force
}
if (-not (Get-NetTCPConnection -State Listen -LocalPort $PgPort -ErrorAction SilentlyContinue)) {
    Write-Ok "Асааж байна..."
    # ЧУХАЛ: pg_ctl-ийн гарцыг PowerShell-ийн дамжуулгад (| Out-Null) оруулж
    # БОЛОХГҮЙ. postgres хүүхэд процесс уг дамжуулгыг өвлөн авдаг тул сервер
    # ажиллаж дуустал pg_ctl хаагдахгүй — скрипт мөнхөд гацна.
    # Хоёр анхаарах зүйл:
    #  1) -o-гийн утга нэг аргумент хэвээр очих ёстой. -ArgumentList-д массив
    #     дамжуулбал PowerShell хоосон зайгаар нь салгачихдаг тул нэг мөр болгоно.
    #  2) pg_ctl-ийг ХҮЛЭЭХГҮЙ (-Wait биш). postgres хүүхэд процесс консолыг
    #     өвлөдөг тул хүлээвэл сервер унтартал скрипт гацна. Оронд нь доорх
    #     `Wait-Postgres` нь pg_isready-гээр бэлэн болохыг хүлээнэ.
    $pgArgs = '-D "{0}" -l "{1}" -o "-p {2} -c listen_addresses=127.0.0.1" start' -f $PgData, $PgLog, $PgPort
    Start-Process -FilePath "$PgBin\pg_ctl.exe" -ArgumentList $pgArgs -WindowStyle Hidden
}

# Аль хэдийн асаалттай байсан ч бэлэн эсэхийг заавал шалгана — өмнөх удаа
# цэвэр бус унтарсан бол сервер сэргээлт хийж байж болно.
if (-not (Wait-Postgres -TimeoutSeconds 60)) {
    Write-Host "    PostgreSQL хариу өгөхгүй байна. Логийн төгсгөл:" -ForegroundColor Red
    if (Test-Path $PgLog) {
        Get-Content $PgLog -Tail 15 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
    } else {
        Write-Host "      Лог олдсонгүй: $PgLog" -ForegroundColor DarkGray
    }
    exit 1
}

$env:PGPASSWORD = "kolonk_dev_2026"
$exists = & "$PgBin\psql.exe" -U kolonk -h 127.0.0.1 -p $PgPort -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='kolonk'"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Өгөгдлийн сан руу холбогдож чадсангүй (psql код $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
if (-not $exists) {
    Invoke-Native "$PgBin\psql.exe" `
        @("-U","kolonk","-h","127.0.0.1","-p","$PgPort","-d","postgres","-c","CREATE DATABASE kolonk OWNER kolonk") `
        "Өгөгдлийн сан үүсгэх"
}
Write-Ok "Ажиллаж байна"

# ── 2. Redis (Memurai) ─────────────────────────────────────────────────────
Write-Step "Redis (6379)"
if (Get-NetTCPConnection -State Listen -LocalPort 6379 -ErrorAction SilentlyContinue) {
    Write-Ok "Ажиллаж байна"
} else {
    $svc = Get-Service Memurai -ErrorAction SilentlyContinue
    if ($svc) { Start-Service Memurai; Write-Ok "Memurai асаалаа" }
    else { Write-Warn "Redis олдсонгүй — насосны телеметр болон фон ажил ажиллахгүй" }
}

# ── 3. Backend ─────────────────────────────────────────────────────────────
Write-Step "Backend (8000)"
if (-not (Test-Path $Python)) {
    Write-Ok "Python орчин үүсгэж байна..."
    py -3.12 -m venv "$Root\backend\.venv"
    & $Python -m pip install --upgrade pip --quiet
    & $Python -m pip install -r "$Root\backend\requirements.txt" --quiet
}
Push-Location "$Root\backend"
Invoke-Native $Python @("-m","alembic","upgrade","head") "Миграц"
Write-Ok "Миграц бэлэн"
if ($Seed) {
    & $Python -m app.seed 2>&1 | ForEach-Object { $_.ToString() }
    if ($LASTEXITCODE -ne 0) { Write-Host "    Seed амжилтгүй" -ForegroundColor Red; exit 1 }
}
Start-Bg $Python @("-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload") "$Root\backend" "api"
Pop-Location
Write-Ok "http://localhost:8000/api/docs"

# ── 3b. Фон ажлын worker (и-баримт, нөөшлөлт, сарын нэхэмжлэх) ─────────────
Write-Step "Worker (ARQ)"
Start-Bg $Python @("-m","arq","app.worker.WorkerSettings") "$Root\backend" "worker"
Write-Ok "Асаалаа"

# ── 4. Frontend ────────────────────────────────────────────────────────────
Write-Step "Frontend (5173)"
if (-not (Test-Path "$Root\frontend\node_modules")) {
    Push-Location "$Root\frontend"; npm install --no-audit --no-fund | Out-Null; Pop-Location
}
Start-Bg "npm.cmd" @("run","dev") "$Root\frontend" "frontend"
Write-Ok "http://localhost:5173"

# ── 5. Бэлэн болохыг хүлээх ────────────────────────────────────────────────
Write-Step "Систем бэлэн болохыг хүлээж байна"

function Wait-Url {
    param([string]$Url, [int]$Seconds = 90)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return $true }
        } catch { Start-Sleep -Milliseconds 800 }
    }
    return $false
}

$apiOk = Wait-Url "http://127.0.0.1:8000/api/health"
if ($apiOk) { Write-Ok "API бэлэн" }
else {
    Write-Host "    API хариу өгсөнгүй. Лог: $LogDir\api.err" -ForegroundColor Red
    exit 1
}

$posOk = Wait-Url "http://localhost:5173" 60
if ($posOk) { Write-Ok "POS бэлэн" }
else { Write-Warn "Frontend удаж байна. Лог: $LogDir\frontend.err" }

Write-Host ""
Write-Host "  Бэлэн боллоо" -ForegroundColor Green
Write-Host "  POS      : http://localhost:5173" -ForegroundColor Green
Write-Host "  API docs : http://localhost:8000/api/docs" -ForegroundColor DarkGray
if ($Quiet) { Write-Host "  Лог      : $LogDir" -ForegroundColor DarkGray }
Write-Host "  Зогсоох  : stop.bat  (эсвэл .\start-dev.ps1 -Stop)" -ForegroundColor DarkGray

if ($Open -and $posOk) { Start-Process "http://localhost:5173" }
