"""Нэвтрэлтийн (auth) Pydantic схемүүд."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BranchInfo(BaseModel):
    """Хэрэглэгчийн харьяалагдах салбар."""

    id: UUID
    code: str
    name: str


class UserTile(BaseModel):
    """Нэвтрэх дэлгэцийн хэрэглэгчийн хайрцаг."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    role_code: str
    role_name_mn: str
    #: Түгээгчийн харьяа салбар (нэвтрэхэд автоматаар сонгогдоно).
    branch: BranchInfo | None = None
    #: True бол хэрэглэгч бүх салбарыг харна (менежер, эзэн).
    all_branches: bool = False


class LoginRequest(BaseModel):
    user_id: UUID
    pin: str


class LoginResponse(BaseModel):
    token: str
    user: UserTile
    permissions: list[str]


class MeResponse(BaseModel):
    user: UserTile
    permissions: list[str]
    shift_open: bool = False
    shift_id: UUID | None = None
    shift_number: int | None = None
