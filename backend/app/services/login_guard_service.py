"""Нэвтрэлтийн хамгаалалт — ПИН таах халдлагыг зогсооно.

Систем интернэтэд гарсан үед 4-6 оронтой ПИН нь бүх боломжийг дараалан
оролдоход эмзэг. Тиймээс хоёр давхар тоолуур ажиллана:

* **Хэрэглэгчээр** — тухайн ажилтны дараалсан алдаа ``USER_MAX_FAILS``
  хүрвэл ``USER_LOCK_SECONDS`` турш нэвтрэх боломжгүй. Амжилттай
  нэвтрэхэд тоолуур тэглэгдэнэ.
* **IP хаягаар** — нэг эх сурвалжаас олон хэрэглэгч дамжуулан оролдохыг
  барина. ``IP_MAX_FAILS`` хүрвэл ``IP_LOCK_SECONDS`` турш хаагдана.

Тоолуурыг Redis-д хадгална: api хэдэн процессоор ажилласан ч нэгдмэл
байх бөгөөд дахин эхлүүлэхэд ч тоолуур алдагдахгүй. Redis унасан үед
нэвтрэлтийг зогсоохгүй (fail-open) — станц ажлаа зогсоохоос сэргийлнэ.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.redis_client import get_redis

#: Нэг ажилтны дараалсан буруу оролдлогын дээд тоо.
USER_MAX_FAILS = 5
#: Хязгаар хэтэрсэн ажилтныг түгжих хугацаа (секунд).
USER_LOCK_SECONDS = 15 * 60

#: Нэг IP хаягаас нийт буруу оролдлогын дээд тоо.
IP_MAX_FAILS = 20
#: Хязгаар хэтэрсэн IP-г хаах хугацаа (секунд).
IP_LOCK_SECONDS = 15 * 60

_USER_KEY = "login:fail:user:{}"
_IP_KEY = "login:fail:ip:{}"


def _minutes(seconds: int) -> int:
    """Хэрэглэгчид харуулах бүхэл минут (доод тал нь 1)."""
    return max(1, (seconds + 59) // 60)


async def _ttl(key: str) -> int:
    try:
        ttl = await get_redis().ttl(key)
    except Exception:  # noqa: BLE001 — Redis унасан бол хүлээлт заахгүй
        return 0
    return ttl if ttl and ttl > 0 else 0


async def check_allowed(user_id: uuid.UUID | None, ip: str | None) -> None:
    """Нэвтрэх оролдлого зөвшөөрөгдөх эсэх. Түгжээтэй бол 429 буцаана."""
    try:
        redis = get_redis()
        checks: list[tuple[str, int]] = []
        if user_id is not None:
            checks.append((_USER_KEY.format(user_id), USER_MAX_FAILS))
        if ip:
            checks.append((_IP_KEY.format(ip), IP_MAX_FAILS))
        if not checks:
            return
        values = await redis.mget([key for key, _ in checks])
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — Redis байхгүй бол хамгаалалтгүй ажиллана
        return

    for (key, limit), raw in zip(checks, values, strict=True):
        if raw is not None and int(raw) >= limit:
            wait = _minutes(await _ttl(key))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Хэт олон удаа буруу оролдлоо. {wait} минутын дараа "
                    "дахин оролдоно уу"
                ),
            )


async def record_failure(user_id: uuid.UUID | None, ip: str | None) -> None:
    """Буруу ПИН — хоёр тоолуурыг ахиулж, хугацааг сунгана."""
    try:
        redis = get_redis()
        pipe = redis.pipeline()
        if user_id is not None:
            key = _USER_KEY.format(user_id)
            pipe.incr(key)
            pipe.expire(key, USER_LOCK_SECONDS)
        if ip:
            key = _IP_KEY.format(ip)
            pipe.incr(key)
            pipe.expire(key, IP_LOCK_SECONDS)
        await pipe.execute()
    except Exception:  # noqa: BLE001
        return


async def record_success(user_id: uuid.UUID, ip: str | None) -> None:
    """Зөв нэвтэрсэн — тухайн ажилтны тоолуур тэглэгдэнэ.

    IP-ийн тоолуурыг ЗОРИУДААР үлдээнэ: халдагч завсар нь нэг зөв ПИН
    таасан ч бусад бүртгэл рүү үргэлжлүүлэн оролдох боломжгүй байх ёстой.
    """
    try:
        await get_redis().delete(_USER_KEY.format(user_id))
    except Exception:  # noqa: BLE001
        return
