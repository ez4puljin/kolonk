#!/usr/bin/env bash
#
# Колонк — өгөгдөл нөөцлөх (Linux). backup-data.ps1-ийн хувилбар.
#
# Гаргах файлууд:
#   kolonk.dump         — өгөгдлийн сангийн бүрэн dump (pg_dump -Fc)
#   kolonk-uploads.tgz  — ээлжийн зураг зэрэг хавсралтууд (байвал)
#
# Эдгээрийг git-ээр биш USB/cloud-оор зөөнө (.gitignore-д орсон).
#
# Хэрэглээ:  ./backup-data.sh [гаргах_хавтас]

set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-.}"
mkdir -p "$OUT"

if ! docker compose ps --status running db --format '{{.Names}}' | grep -q .; then
  echo "db контейнер ажиллахгүй байна — эхлээд ./deploy.sh ажиллуулна уу." >&2
  exit 1
fi

echo "==> Сангийн dump авч байна"
docker compose exec -T db pg_dump -Fc -U kolonk -d kolonk > "$OUT/kolonk.dump"
echo "    $OUT/kolonk.dump ($(du -h "$OUT/kolonk.dump" | cut -f1))"

# Хавсралтууд нэрлэсэн volume дотор — түр контейнероор гаргаж авна.
if docker volume ls --format '{{.Name}}' | grep -q '_uploads$'; then
  echo "==> Хавсралтуудыг багцалж байна"
  VOL=$(docker volume ls --format '{{.Name}}' | grep -m1 '_uploads$')
  docker run --rm -v "$VOL":/data -v "$(cd "$OUT" && pwd)":/out alpine \
    tar czf /out/kolonk-uploads.tgz -C /data . 2>/dev/null || true
  [ -f "$OUT/kolonk-uploads.tgz" ] && \
    echo "    $OUT/kolonk-uploads.tgz ($(du -h "$OUT/kolonk-uploads.tgz" | cut -f1))"
fi

echo
echo "Нөөцлөлт бэлэн. Эдгээр файлыг USB эсвэл cloud-оор зөөнө үү."
