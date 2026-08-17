"""Нэвтрэлтийн хамгаалалтын тест — ПИН таах халдлагыг зогсоох логик.

Бодит Redis **хэрэглэхгүй**: `get_redis`-г санах ойн хуурамч биетээр
орлуулж, тоолуур/түгжээ/тэглэлт зөв ажиллаж буйг шалгана.

Ажиллуулах:  ``pytest app/tests/test_login_guard.py``
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.services import login_guard_service as guard

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER = uuid.UUID("22222222-2222-2222-2222-222222222222")
IP = "203.0.113.7"


class _FakePipeline:
    def __init__(self, store: dict[str, int], ttls: dict[str, int]) -> None:
        self._store = store
        self._ttls = ttls
        self._ops: list[tuple[str, str, int]] = []

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key, 0))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key, seconds))

    async def execute(self) -> None:
        for op, key, seconds in self._ops:
            if op == "incr":
                self._store[key] = self._store.get(key, 0) + 1
            else:
                self._ttls[key] = seconds
        self._ops.clear()


class _FakeRedis:
    """Тоолуур хадгалах хамгийн бага Redis — mget/ttl/pipeline/delete."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [None if key not in self.store else str(self.store[key]) for key in keys]

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -2)

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.store, self.ttls)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr(guard, "get_redis", lambda: fake)
    return fake


async def _fail(times: int, user_id: uuid.UUID | None = USER, ip: str | None = IP) -> None:
    for _ in range(times):
        await guard.record_failure(user_id, ip)


@pytest.mark.asyncio
async def test_clean_state_allows_login(redis: _FakeRedis) -> None:
    await guard.check_allowed(USER, IP)  # алдаа гарахгүй


@pytest.mark.asyncio
async def test_under_limit_still_allowed(redis: _FakeRedis) -> None:
    await _fail(guard.USER_MAX_FAILS - 1)
    await guard.check_allowed(USER, IP)


@pytest.mark.asyncio
async def test_user_locked_after_max_fails(redis: _FakeRedis) -> None:
    await _fail(guard.USER_MAX_FAILS)
    with pytest.raises(HTTPException) as err:
        await guard.check_allowed(USER, IP)
    assert err.value.status_code == 429
    # Хүлээх хугацааг минутаар хэлнэ.
    assert "минут" in err.value.detail


@pytest.mark.asyncio
async def test_lock_is_per_user_not_global(redis: _FakeRedis) -> None:
    """Нэг ажилтан түгжигдсэн нь бусдыг зогсоохгүй (IP хязгаар хүрээгүй)."""
    await _fail(guard.USER_MAX_FAILS, user_id=USER, ip=None)
    with pytest.raises(HTTPException):
        await guard.check_allowed(USER, None)
    await guard.check_allowed(OTHER, None)


@pytest.mark.asyncio
async def test_success_clears_user_counter(redis: _FakeRedis) -> None:
    await _fail(guard.USER_MAX_FAILS - 1)
    await guard.record_success(USER, IP)
    await _fail(guard.USER_MAX_FAILS - 1)
    # Тэглэгдсэн тул дахин хязгаарт хүрээгүй.
    await guard.check_allowed(USER, IP)


@pytest.mark.asyncio
async def test_success_keeps_ip_counter(redis: _FakeRedis) -> None:
    """Завсарт нэг зөв ПИН таасан ч IP-ийн тоолуур тэглэгдэхгүй."""
    await _fail(guard.IP_MAX_FAILS)
    await guard.record_success(USER, IP)
    with pytest.raises(HTTPException):
        await guard.check_allowed(OTHER, IP)


@pytest.mark.asyncio
async def test_ip_limit_blocks_user_rotation(redis: _FakeRedis) -> None:
    """Хэрэглэгч сольж оролдох халдлагыг IP тоолуур барина."""
    for index in range(guard.IP_MAX_FAILS):
        await guard.record_failure(uuid.uuid4(), IP)
        assert index < guard.IP_MAX_FAILS
    with pytest.raises(HTTPException) as err:
        await guard.check_allowed(uuid.uuid4(), IP)
    assert err.value.status_code == 429


@pytest.mark.asyncio
async def test_redis_down_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis унасан үед станц ажлаа зогсоохгүй — хамгаалалтгүй ч нэвтэрнэ."""

    def _broken() -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(guard, "get_redis", _broken)
    await guard.check_allowed(USER, IP)
    await guard.record_failure(USER, IP)
    await guard.record_success(USER, IP)
