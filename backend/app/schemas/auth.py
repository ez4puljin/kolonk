"""Нэвтрэлтийн (auth) Pydantic схемүүд."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BranchInfo(BaseModel):
    """Хэрэглэгчийн ажлын салбар."""

    id: UUID
    code: str
    name: str


class LoginBranch(BaseModel):
    """Нэвтрэх дэлгэцийн салбарын хайрцаг (нэвтрэх шаардлагагүй)."""

    id: UUID
    code: str
    name: str
    address: str | None = None
    #: Тухайн салбарт одоо ээлж нээлттэй бол нээсэн хүний нэр — ажилдаа
    #: ирж буй түгээгч хэн ажиллаж байгааг нэвтрэхээсээ өмнө харна.
    open_shift_by: str | None = None
    #: Салбарт харьяалагдах идэвхтэй ажилтны тоо.
    staff_count: int = 0


class UserTile(BaseModel):
    """Нэвтрэх дэлгэцийн хэрэглэгчийн хайрцаг."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    username: str
    role_code: str
    role_name_mn: str
    #: АЖЛЫН салбар: түгээгчийн харьяа салбар, эсвэл салбаргүй хэрэглэгчийн
    #: нэвтрэхдээ сонгосон салбар. Сонгоогүй админд `None`.
    branch: BranchInfo | None = None
    #: True бол салбар нь өгөгдлийн санд хатуу заагдсан (түгээгч) — солих
    #: боломжгүй. False бол нэвтрэхдээ сонгосон, толгой хэсгээс солино.
    branch_locked: bool = False
    #: True бол хэрэглэгч бүх салбарыг харна (нягтлан, админ).
    all_branches: bool = False


class LoginRequest(BaseModel):
    user_id: UUID
    pin: str
    #: Нэвтрэхдээ сонгосон салбар. Түгээгчид өгвөл өөрийнхтэй нь таарах
    #: ёстой; салбаргүй хэрэглэгчид ажлын салбар болно; админд заавал биш.
    branch_id: UUID | None = None


class SwitchBranchRequest(BaseModel):
    """Нэвтэрсэн салбаргүй хэрэглэгч ажлын салбараа солих (`None` = бүх салбар)."""

    branch_id: UUID | None = None


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
