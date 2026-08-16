"""Системийн схемүүд — тохиргоо, аудит лог, ерөнхий хариултууд."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class OkResponse(BaseModel):
    ok: bool = True


class SettingOut(BaseModel):
    key: str
    value: Any = None
    description: str | None = None


class SettingUpdate(BaseModel):
    value: Any = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_full_name: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
