"""Хэрэглэгч, дүр, эрхийн схемүүд."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str
    role_id: uuid.UUID
    role_code: str
    role_name_mn: str
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    phone: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int


class UserCreate(BaseModel):
    username: str
    full_name: str
    pin: str
    role_id: uuid.UUID
    phone: str | None = None
    #: Түгээгчд ЗААВАЛ — тухайн хүн нэг салбарт ажиллана.
    #: Менежер, эзэнд хоосон (бүх салбарыг хардаг).
    branch_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    branch_id: uuid.UUID | None = None
    username: str | None = None
    full_name: str | None = None
    role_id: uuid.UUID | None = None
    phone: str | None = None
    is_active: bool | None = None


class ResetPinRequest(BaseModel):
    pin: str


class RoleOut(BaseModel):
    id: uuid.UUID
    code: str
    name_mn: str
    permissions: list[str] = []
    user_count: int = 0


class RoleListResponse(BaseModel):
    items: list[RoleOut]
    total: int


class PermissionOut(BaseModel):
    code: str
    name_mn: str


class PermissionGroup(BaseModel):
    key: str
    name_mn: str
    items: list[PermissionOut]


class PermissionGroupListResponse(BaseModel):
    groups: list[PermissionGroup]
    total: int


class RolePermissionsUpdate(BaseModel):
    codes: list[str]
