#!/usr/bin/env bash
#
# Колонк — нөөцлөсөн өгөгдлийг сэргээх (Linux). restore-data.ps1-ийн хувилбар.
#
# Урьдчилсан нөхцөл: ./deploy.sh ажиллаж дууссан (db контейнер асаалттай).
#
# АНХААР: энэ нь одоогийн сангийн агуулгыг ДАРЖ БИЧНЭ.
#
# Хэрэглээ:  ./restore-data.sh [dump_файлын_зам]

set -euo pipefail
cd "$(dirname "$0")"

DUMP="${1:-kolonk.dump}"
[ -f "$DUMP" ] || { echo "Файл олдсонгүй: $DUMP" >&2; exit 1; }

if ! docker compose ps --status running db --format '{{.Names}}' | grep -q .; then
  echo "db контейнер ажиллахгүй байна — эхлээд ./deploy.sh ажиллуулна уу." >&2
  exit 1
fi

echo "АНХААР: одоогийн өгөгдлийн сан ДАРАГДАНА."
read -r -p "Үргэлжлүүлэх үү? (тийм гэж бичнэ үү): " answer
[ "$answer" = "тийм" ] || { echo "Цуцлагдав."; exit 1; }

echo "==> Dump-ыг контейнер руу хуулж байна"
docker compose cp "$DUMP" db:/tmp/kolonk.dump

echo "==> Сэргээж байна"
docker compose exec -T db pg_restore --clean --if-exists --no-owner \
  -U kolonk -d kolonk /tmp/kolonk.dump
docker compose exec -T db rm -f /tmp/kolonk.dump

# Хавсралтууд байвал буцааж дүүргэнэ.
if [ -f kolonk-uploads.tgz ] && docker volume ls --format '{{.Name}}' | grep -q '_uploads$'; then
  echo "==> Хавсралтуудыг сэргээж байна"
  VOL=$(docker volume ls --format '{{.Name}}' | grep -m1 '_uploads$')
  docker run --rm -v "$VOL":/data -v "$(pwd)":/in alpine \
    sh -c 'tar xzf /in/kolonk-uploads.tgz -C /data'
fi

echo "==> Миграцийг дуустал нь ажиллуулж байна"
docker compose restart api-prod worker >/dev/null

echo
echo "Сэргээлт дууслаа."
