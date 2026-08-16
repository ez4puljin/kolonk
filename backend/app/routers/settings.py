"""Системийн тохиргоо."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.system import SettingOut, SettingUpdate
from app.services import settings_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["settings"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


@router.get("/settings", response_model=dict[str, Any])
async def get_settings(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Бүх тохиргоо `{түлхүүр: утга}` хэлбэрээр."""
    await settings_service.ensure_settings(db)
    return await settings_service.get_all(db)


@router.put("/settings/{key}", response_model=SettingOut)
async def update_setting(
    request: Request,
    payload: SettingUpdate,
    key: str = Path(description="Тохиргооны түлхүүр"),
    current: User = Depends(require_permission("settings.manage")),
    db: AsyncSession = Depends(get_db),
) -> SettingOut:
    key = key.strip()
    if not key or len(key) > 64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Тохиргооны түлхүүр буруу байна (1-64 тэмдэгт)",
        )
    old_value, row = await settings_service.set_setting(db, key, payload.value)

    await audit(
        db,
        user_id=current.id,
        action="setting.update",
        entity_type="setting",
        entity_id=row.id,
        before={"key": key, "value": old_value},
        after={"key": key, "value": payload.value},
        ip=_client_ip(request),
    )
    return SettingOut(key=row.key, value=payload.value, description=row.description)
