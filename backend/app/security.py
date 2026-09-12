from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.config import settings


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except ValueError:
        return False


def create_token(user_id: UUID, role_code: str, branch_id: UUID | None = None) -> str:
    """Нэвтрэлтийн токен.

    ``branch_id`` — нэвтрэхдээ сонгосон АЖЛЫН салбар (``bid`` claim). Салбаргүй
    хэрэглэгч (нягтлан, админ) салбар сонгож нэвтрэхэд серверийн салбарын
    логик (ээлж нээх, зардал, орлого) энэ салбарыг ашиглана. Түгээгчийн
    салбар өгөгдлийн санд байдаг тул токенд давхар бичихгүй.
    """
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "role": role_code,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expire_hours)).timestamp()),
    }
    if branch_id is not None:
        payload["bid"] = str(branch_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
