#!/usr/bin/env bash
#
# Колонк — production руу нэг командаар гаргах (Linux).
#
# deploy.ps1-ийн Линукс хувилбар. Хоёр алдаанаас хамгаална:
#   1. nginx эсвэл api-prod дахин үүсэхэд cloudflared унтарч, систем
#      интернэтээс тасардаг. Дотоод сүлжээнд бүх юм хэвийн харагддаг
#      тул анзаарагдахгүй өнгөрдөг.
#   2. Гаргасны дараа юу ч шалгадаггүй — эвдэрсэн эсэхийг ажилтан
#      залгаж хэлж байж мэддэг.
#
# Хэрэглээ:
#   ./deploy.sh                 бүгдийг барьж, тест ажлуулж, гаргаад шалгана
#   ./deploy.sh --frontend      зөвхөн frontend (хурдан)
#   ./deploy.sh --backend       зөвхөн backend
#   ./deploy.sh --skip-tests    тест алгасана
#   PUBLIC_URL=https://... ./deploy.sh    гадаад шалгалтын хаяг

set -euo pipefail
cd "$(dirname "$0")"

BACKEND=0
FRONTEND=0
SKIP_TESTS=0
PUBLIC_URL="${PUBLIC_URL:-https://pos.puljika.site}"

for arg in "$@"; do
  case "$arg" in
    --backend)    BACKEND=1 ;;
    --frontend)   FRONTEND=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    *) echo "Танихгүй сонголт: $arg" >&2; exit 1 ;;
  esac
done
if [ "$BACKEND" -eq 0 ] && [ "$FRONTEND" -eq 0 ]; then BACKEND=1; FRONTEND=1; fi

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; OFF='\033[0m'
step() { printf "\n${CYAN}==> %s${OFF}\n" "$1"; }
fail() { printf "\n${RED}ЗОГСЛОО: %s${OFF}\n" "$1"; exit 1; }

# --- 0. Docker ------------------------------------------------------------
step "Docker engine шалгаж байна"
docker version --format '{{.Server.Version}}' >/dev/null 2>&1 \
  || fail "Docker engine асаагүй байна. sudo systemctl start docker"
echo "    engine $(docker version --format '{{.Server.Version}}')"

# --- 1. Тест --------------------------------------------------------------
if [ "$SKIP_TESTS" -eq 0 ] && [ "$BACKEND" -eq 1 ]; then
  step "Backend тест"
  docker compose --profile dev up -d api >/dev/null
  if out=$(docker compose exec -T api pytest -q); then
    echo "    $(echo "$out" | tail -1)"
  else
    docker compose stop api >/dev/null
    fail "Тест унасан:\n$out"
  fi
  docker compose stop api >/dev/null
fi

# --- 2. Барих -------------------------------------------------------------
SERVICES=()
[ "$BACKEND" -eq 1 ]  && SERVICES+=(api-prod worker)
[ "$FRONTEND" -eq 1 ] && SERVICES+=(nginx)

step "Барьж байна: ${SERVICES[*]}"
docker compose build "${SERVICES[@]}" || fail "Build амжилтгүй."

# --- 3. Гаргах ------------------------------------------------------------
# ЧУХАЛ: prod ба tunnel профайлыг ҮРГЭЛЖ хамт өргөнө. Зөвхөн nginx-ийг
# өргөвөл cloudflared унтарч, систем интернэтээс тасардаг.
step "Гаргаж байна (prod + tunnel)"
docker compose --profile prod --profile tunnel up -d || fail "Хөөргөх амжилтгүй."

# --- 4. Шалгах ------------------------------------------------------------
step "Шалгаж байна"
NET=$(docker network ls --format '{{.Name}}' | grep -m1 kolonk)

check() { # нэр, url, [--network]
  local label="$1" url="$2"; shift 2
  local code=""
  for _ in $(seq 1 10); do
    sleep 3
    code=$(docker run --rm "$@" curlimages/curl:latest -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)
    if [ "$code" = "200" ]; then printf "    ${GREEN}%s HTTP 200${OFF}\n" "$label"; return 0; fi
  done
  printf "    ${RED}%s HTTP %s${OFF}\n" "$label" "${code:-—}"
  return 1
}

ok=0
check "Дотоод (хуудас) :" "http://nginx/"           --network "$NET" || ok=1
check "Дотоод (API)    :" "http://nginx/api/health" --network "$NET" || ok=1
check "Гадаад (tunnel) :" "$PUBLIC_URL/api/health"                   || ok=1

echo
if [ "$ok" -eq 0 ]; then
  printf "${GREEN}Гарлаа. Систем интернэтээс хэвийн ажиллаж байна.${OFF}\n"
else
  printf "${RED}Гарсан ч ШАЛГАЛТ УНАСАН — доорх логийг хараарай:${OFF}\n"
  docker compose logs --tail 20 nginx api-prod cloudflared
  exit 1
fi
