import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security import decode_token

CredentialsError = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Нэвтрэх эрх хүчингүй байна",
    headers={"WWW-Authenticate": "Bearer"},
)


async def load_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise CredentialsError
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise CredentialsError
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:  # noqa: BLE001
        raise CredentialsError from exc
    return await load_user(db, user_id)


def user_permissions(user: User) -> set[str]:
    return {rp.permission.code for rp in user.role.permissions}


def require_permission(*codes: str) -> Callable:
    """Dependency factory — user must hold at least one of the given codes."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        granted = user_permissions(user)
        if not granted.intersection(codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Танд '{codes[0]}' эрх байхгүй байна",
            )
        return user

    return _guard
