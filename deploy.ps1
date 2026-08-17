<#
.SYNOPSIS
    Колонк — production руу нэг командаар гаргах.

.DESCRIPTION
    Гараар `docker compose build ... ; up -d ...` бичихэд хоёр алдаа
    байнга давтагддаг:

      1. nginx эсвэл api-prod дахин үүсэхэд `cloudflared` унтарч,
         систем интернэтээс тасардаг. Дотоод сүлжээнд бүх юм хэвийн
         харагддаг тул анзаарагдахгүй өнгөрдөг.
      2. Гаргасны дараа юу ч шалгадаггүй — эвдэрсэн эсэхийг ажилтан
         залгаж хэлж байж мэддэг.

    Энэ скрипт хоёуланг нь хаана: prod + tunnel профайлыг ҮРГЭЛЖ хамт
    өргөж, төгсгөлд нь дотоод болон ГАДААД хаягийг шалгана.

    Тайлбар: native командын гаралтыг `2>&1`-ээр барихгүй. PowerShell
    5.1 нь docker-ийн явцын мөрийг (stderr) алдаа болгож хувиргадаг тул
    амжилтыг зөвхөн $LASTEXITCODE-оор шалгана.

.PARAMETER Backend
    Зөвхөн backend-ийг (api-prod, worker) дахин барина.

.PARAMETER Frontend
    Зөвхөн frontend-ийг (nginx) дахин барина.

.PARAMETER SkipTests
    pytest-ийг алгасана (анхдагчаар ажиллуулна).

.PARAMETER PublicUrl
    Гадаад шалгалтын хаяг. Домэйн солигдвол энд дамжуулна.

.EXAMPLE
    .\deploy.bat
    Бүгдийг барьж, тест ажлуулж, гаргаад шалгана.

.EXAMPLE
    .\deploy.bat -Frontend
    Зөвхөн frontend өөрчлөгдсөн үед — хурдан.
#>
[CmdletBinding()]
param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$SkipTests,
    [string]$PublicUrl = 'https://pos.puljika.site'
)

Set-Location -LiteralPath $PSScriptRoot

# Аль нэгийг ч заагаагүй бол хоёуланг нь.
if (-not $Backend -and -not $Frontend) { $Backend = $true; $Frontend = $true }

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Fail([string]$Text) {
    Write-Host ''
    Write-Host "ЗОГСЛОО: $Text" -ForegroundColor Red
    exit 1
}

# --- 0. Docker ажиллаж байна уу ------------------------------------------
Write-Step 'Docker engine шалгаж байна'
$version = docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0) {
    Fail 'Docker engine асаагүй байна. Docker Desktop-оо нээгээд дахин оролдоно уу.'
}
Write-Host "    engine $version"

# --- 1. Тест --------------------------------------------------------------
if (-not $SkipTests -and $Backend) {
    Write-Step 'Backend тест'
    docker compose --profile dev up -d api | Out-Null
    $out = docker compose exec -T api pytest -q | Out-String
    $code = $LASTEXITCODE
    docker compose stop api | Out-Null
    if ($code -ne 0) { Fail "Тест унасан:`n$out" }
    if ($out -match '(\d+) passed') { Write-Host "    $($Matches[0])" } else { Write-Host '    OK' }
}

# --- 2. Барих -------------------------------------------------------------
$services = @()
if ($Backend) { $services += @('api-prod', 'worker') }
if ($Frontend) { $services += 'nginx' }

Write-Step "Барьж байна: $($services -join ', ')"
docker compose build @services
if ($LASTEXITCODE -ne 0) { Fail 'Build амжилтгүй.' }

# --- 3. Гаргах ------------------------------------------------------------
# ЧУХАЛ: prod ба tunnel профайлыг ҮРГЭЛЖ хамт өргөнө. Зөвхөн nginx-ийг
# өргөвөл cloudflared унтарч, систем интернэтээс тасардаг.
Write-Step 'Гаргаж байна (prod + tunnel)'
docker compose --profile prod --profile tunnel up -d
if ($LASTEXITCODE -ne 0) { Fail 'Хөөргөх амжилтгүй.' }

# --- 4. Шалгах ------------------------------------------------------------
Write-Step 'Шалгаж байна'
$net = (docker network ls --format '{{.Name}}' | Select-String 'kolonk' | Select-Object -First 1).ToString().Trim()

function Test-Url {
    param([string]$Label, [string]$Url, [string[]]$ExtraArgs = @())

    $code = ''
    foreach ($attempt in 1..10) {
        Start-Sleep -Seconds 3
        $code = (docker run --rm @ExtraArgs curlimages/curl:latest -s -o /dev/null -w '%{http_code}' $Url | Out-String).Trim()
        if ($code -eq '200') {
            Write-Host "    $Label HTTP 200" -ForegroundColor Green
            return $true
        }
    }
    Write-Host "    $Label HTTP $code" -ForegroundColor Red
    return $false
}

$okWeb = Test-Url 'Дотоод (хуудас) :' 'http://nginx/'              @('--network', $net)
$okApi = Test-Url 'Дотоод (API)    :' 'http://nginx/api/health'    @('--network', $net)
$okPub = Test-Url 'Гадаад (tunnel) :' "$PublicUrl/api/health"

Write-Host ''
if ($okWeb -and $okApi -and $okPub) {
    Write-Host 'Гарлаа. Систем интернэтээс хэвийн ажиллаж байна.' -ForegroundColor Green
    exit 0
}

Write-Host 'Гарсан ч ШАЛГАЛТ УНАСАН — доорх логийг хараарай:' -ForegroundColor Red
docker compose logs --tail 20 nginx api-prod cloudflared
exit 1
