"""Хэрэглэгч, дүр, эрхийн удирдлага."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission, user_permissions
from app.enums import RoleCode
from app.models.branch import Branch
from app.models.user import Permission, Role, RolePermission, User
from app.permissions import PERMISSIONS, ROLE_NAMES_MN
from app.schemas.system import OkResponse
from app.schemas.user import (
    PermissionGroup,
    PermissionGroupListResponse,
    PermissionOut,
    ResetPinRequest,
    RoleListResponse,
    RoleOut,
    RolePermissionsUpdate,
    UserCreate,
    UserListResponse,
    UserOut,
    UserUpdate,
)
from app.security import hash_pin
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["users"])

PERMISSION_GROUP_NAMES_MN: dict[str, str] = {
    "sales": "Борлуулалт",
    "shifts": "Ээлж",
    "tanks": "Сав",
    "pumps": "Насос",
    "products": "Бараа",
    "inventory": "Нөөц",
    "prices": "Үнэ",
    "receipts": "Шатахуун таталт",
    "purchases": "Худалдан авалт",
    "suppliers": "Нийлүүлэгч",
    "contracts": "Гэрээ",
    "instruments": "Ваучер, карт",
    "accounting": "Нягтлан бодох бүртгэл",
    "reports": "Тайлан",
    "dashboard": "Хяналтын самбар",
    "users": "Хэрэглэгч",
    "settings": "Тохиргоо",
    "backup": "Нөөцлөлт",
    "audit": "Аудит",
    "ebarimt": "И-баримт",
}


# ---------------------------------------------------------------------------
# Туслах функцууд
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def _role_name(role: Role) -> str:
    return role.name_mn or ROLE_NAMES_MN.get(role.code, role.code)


async def _resolve_branch(db: AsyncSession, role: Role, branch_id) -> "Branch | None":
    """Түгээгчд салбар ЗААВАЛ; менежер, эзэнд салбар хамаарахгүй.

    Менежер/эзэн бүх салбарыг хардаг тул тэдэнд салбар оноох нь утгагүй —
    санамсаргүй илгээсэн ч хоосон болгоно.
    """
    if str(role.code) in (str(RoleCode.MANAGER), str(RoleCode.OWNER)):
        return None
    if branch_id is None:
        raise HTTPException(status_code=422, detail="Түгээгчд салбар заавал сонгоно")
    branch = await db.get(Branch, branch_id)
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй")
    return branch


def _user_out(user: User, role: Role, branch_name: str | None = None) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role_id=role.id,
        role_code=role.code,
        role_name_mn=_role_name(role),
        branch_id=user.branch_id,
        branch_name=branch_name,
        phone=user.phone,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _snapshot(user: User, role: Role) -> dict[str, Any]:
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role_code": role.code,
        "phone": user.phone,
        "is_active": user.is_active,
    }


def _validate_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ПИН код зөвхөн 4-6 оронтой тоо байх ёстой",
        )
    return pin


def _validate_text(value: str, field_mn: str, max_len: int) -> str:
    value = (value or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_mn} хоосон байж болохгүй",
        )
    if len(value) > max_len:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_mn} хэт урт байна ({max_len} тэмдэгтээс бага байх ёстой)",
        )
    return value


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Хэрэглэгч олдсонгүй")
    return user


async def _get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Дүр олдсонгүй")
    return role


async def _assert_username_free(db: AsyncSession, username: str, exclude_id: uuid.UUID | None = None) -> None:
    """Нэвтрэх нэр давхардсан бол аль салбарт бүртгэлтэйг нь хэлнэ.

    Нэг түгээгч хоёр салбарт бүртгэгдэж болохгүй — давхар бүртгэл үүсгэх гэж
    байгааг нь салбарын нэрээр нь тодорхой хэлж сануулна.
    """
    stmt = select(User).where(func.lower(User.username) == username.lower())
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    clash = await db.scalar(stmt)
    if clash is None:
        return

    branch_name = None
    if clash.branch_id:
        branch = await db.get(Branch, clash.branch_id)
        branch_name = branch.name if branch else None

    where = f"'{branch_name}' салбарт" if branch_name else "салбаргүйгээр"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"'{clash.username}' нэртэй хэрэглэгч {where} аль хэдийн бүртгэлтэй байна "
            f"({clash.full_name}). Нэг ажилтныг хоёр салбарт бүртгэх боломжгүй."
        ),
    )


async def _assert_branch_change_ok(db: AsyncSession, user: User, new_branch) -> None:
    """Түгээгчийн салбар солих боломжтой эсэх.

    Нээлттэй ээлжтэй байхад салбар солих нь ээлжийн тайланг хоёр салбарт
    хуваана — тиймээс хориглоно. Ээлж хаалттай үед чөлөөтэй шилжүүлнэ.
    """
    if new_branch is None or user.branch_id == new_branch.id:
        return

    from app.enums import ShiftStatus
    from app.models.shift import Shift

    open_shift = await db.scalar(
        select(func.count())
        .select_from(Shift)
        .where(Shift.opened_by == user.id, Shift.status == str(ShiftStatus.OPEN))
    )
    if open_shift:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Нээлттэй ээлжтэй байхад салбар солих боломжгүй. Эхлээд ээлжээ хаана уу",
        )

    # Өмнө нь "эхлээд одоогийн салбараас нь чөлөөлнө үү" гэж хориглож байсан.
    # Тэр зөвлөмж ХҮРЭХ АРГАГҮЙ байв: PATCH нь `branch_id: null`-ыг талбар
    # огт өгөөгүйгээс ялгаж чаддаггүй, ялгасан ч түгээгчид салбар заавал
    # шаардлагатай тул хоосон болгож болдоггүй. Үр дүнд нь буруу салбарт
    # бүртгэгдсэн түгээгчийг ХЭЗЭЭ Ч зөөж чаддаггүй байлаа.
    #
    # Бодит эрсдэл нь дээрх нээлттэй ээлж — тэр шалгуур хэвээр үлдэнэ.


async def _active_owner_count(db: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.code == RoleCode.OWNER, User.is_active.is_(True))
    )
    return int((await db.scalar(stmt)) or 0)


async def _assert_not_last_owner(db: AsyncSession, user: User, role: Role) -> None:
    if role.code != RoleCode.OWNER or not user.is_active:
        return
    if await _active_owner_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сүүлчийн идэвхтэй эзний бүртгэлийг хаах боломжгүй",
        )


# ---------------------------------------------------------------------------
# Хэрэглэгч
# ---------------------------------------------------------------------------


@router.get("/users", response_model=UserListResponse)
async def list_users(
    is_active: bool | None = Query(default=None),
    role_code: str | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None, description="Салбараар шүүх"),
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """Хэрэглэгчийн жагсаалт. `users.manage` эрхгүй хэрэглэгч зөвхөн идэвхтэйг харна."""
    conditions = []
    if "users.manage" not in user_permissions(current):
        conditions.append(User.is_active.is_(True))
    elif is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if role_code:
        conditions.append(Role.code == role_code)
    if branch_id is not None:
        conditions.append(User.branch_id == branch_id)
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(User.full_name.ilike(pattern) | User.username.ilike(pattern))

    total_stmt = select(func.count()).select_from(User).join(Role, User.role_id == Role.id)
    if conditions:
        total_stmt = total_stmt.where(*conditions)
    total = int((await db.scalar(total_stmt)) or 0)

    stmt = select(User).join(Role, User.role_id == Role.id)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(User.full_name).limit(limit).offset(offset)
    users = (await db.scalars(stmt)).all()

    branch_names = {
        b.id: b.name for b in (await db.scalars(select(Branch))).all()
    }
    return UserListResponse(
        items=[_user_out(u, u.role, branch_names.get(u.branch_id)) for u in users],
        total=total,
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    username = _validate_text(payload.username, "Нэвтрэх нэр", 64)
    full_name = _validate_text(payload.full_name, "Овог нэр", 128)
    pin = _validate_pin(payload.pin)
    role = await _get_role(db, payload.role_id)
    await _assert_username_free(db, username)
    branch = await _resolve_branch(db, role, payload.branch_id)

    user = User(
        username=username,
        full_name=full_name,
        pin_hash=hash_pin(pin),
        role_id=role.id,
        branch_id=branch.id if branch else None,
        phone=(payload.phone or "").strip() or None,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, ["created_at", "updated_at"])

    await audit(
        db,
        user_id=current.id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        after=_snapshot(user, role),
        ip=_client_ip(request),
    )
    branch_name = None
    if user.branch_id:
        row = await db.get(Branch, user.branch_id)
        branch_name = row.name if row else None
    return _user_out(user, role, branch_name)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user(db, user_id)
    role = user.role
    before = _snapshot(user, role)
    data = payload.model_dump(exclude_unset=True)

    if "username" in data and data["username"] is not None:
        username = _validate_text(data["username"], "Нэвтрэх нэр", 64)
        await _assert_username_free(db, username, exclude_id=user.id)
        user.username = username
    if "full_name" in data and data["full_name"] is not None:
        user.full_name = _validate_text(data["full_name"], "Овог нэр", 128)
    if "phone" in data:
        user.phone = (data["phone"] or "").strip() or None
    if "role_id" in data and data["role_id"] is not None and data["role_id"] != user.role_id:
        if role.code == RoleCode.OWNER and user.is_active and await _active_owner_count(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Сүүлчийн идэвхтэй эзний дүрийг өөрчлөх боломжгүй",
            )
        role = await _get_role(db, data["role_id"])
        user.role_id = role.id
    if "is_active" in data and data["is_active"] is not None:
        if data["is_active"] is False:
            await _assert_not_last_owner(db, user, role)
        user.is_active = data["is_active"]

    await db.flush()
    await db.refresh(user, ["created_at", "updated_at"])

    await audit(
        db,
        user_id=current.id,
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=_snapshot(user, role),
        ip=_client_ip(request),
    )
    # Салбар солих (түгээгчд заавал, менежер/эзэнд хоосон болно)
    if payload.branch_id is not None or payload.role_id is not None:
        branch = await _resolve_branch(db, role, payload.branch_id or user.branch_id)
        # Салбар солих гэж байвал одоогийн харьяаллыг нь сануулна.
        if payload.branch_id is not None:
            await _assert_branch_change_ok(db, user, branch)
        user.branch_id = branch.id if branch else None
        await db.flush()

    branch_name = None
    if user.branch_id:
        row = await db.get(Branch, user.branch_id)
        branch_name = row.name if row else None
    return _user_out(user, role, branch_name)


@router.delete("/users/{user_id}", response_model=OkResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    """Зөөлөн устгал — хэрэглэгчийг идэвхгүй болгоно."""
    user = await _get_user(db, user_id)
    role = user.role
    before = _snapshot(user, role)
    await _assert_not_last_owner(db, user, role)

    user.is_active = False
    await db.flush()

    await audit(
        db,
        user_id=current.id,
        action="user.delete",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={**before, "is_active": False},
        ip=_client_ip(request),
    )
    return OkResponse()


@router.post("/users/{user_id}/reset-pin", response_model=OkResponse)
async def reset_pin(
    user_id: uuid.UUID,
    payload: ResetPinRequest,
    request: Request,
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    user = await _get_user(db, user_id)
    pin = _validate_pin(payload.pin)
    user.pin_hash = hash_pin(pin)
    await db.flush()

    await audit(
        db,
        user_id=current.id,
        action="user.reset_pin",
        entity_type="user",
        entity_id=user.id,
        after={"username": user.username, "pin_reset": True},
        ip=_client_ip(request),
    )
    return OkResponse()


# ---------------------------------------------------------------------------
# Дүр ба эрх
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> RoleListResponse:
    roles = (await db.scalars(select(Role).order_by(Role.code))).all()
    counts_rows = await db.execute(
        select(User.role_id, func.count()).where(User.is_active.is_(True)).group_by(User.role_id)
    )
    counts = {row[0]: int(row[1]) for row in counts_rows.all()}
    items = [
        RoleOut(
            id=role.id,
            code=role.code,
            name_mn=_role_name(role),
            permissions=sorted(rp.permission.code for rp in role.permissions),
            user_count=counts.get(role.id, 0),
        )
        for role in roles
    ]
    return RoleListResponse(items=items, total=len(items))


@router.get("/permissions", response_model=PermissionGroupListResponse)
async def list_permissions(
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> PermissionGroupListResponse:
    rows = (await db.scalars(select(Permission).order_by(Permission.code))).all()
    catalog: list[tuple[str, str]] = [(p.code, p.name_mn) for p in rows]
    if not catalog:
        catalog = sorted(PERMISSIONS.items())

    grouped: dict[str, list[PermissionOut]] = {}
    for code, name_mn in catalog:
        key = code.split(".", 1)[0]
        grouped.setdefault(key, []).append(PermissionOut(code=code, name_mn=name_mn))

    groups = [
        PermissionGroup(key=key, name_mn=PERMISSION_GROUP_NAMES_MN.get(key, key), items=items)
        for key, items in grouped.items()
    ]
    return PermissionGroupListResponse(groups=groups, total=len(catalog))


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdate,
    request: Request,
    current: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
) -> RoleOut:
    role = await _get_role(db, role_id)
    before_codes = sorted(rp.permission.code for rp in role.permissions)

    wanted = sorted({code.strip() for code in payload.codes if code and code.strip()})
    perms = (await db.scalars(select(Permission).where(Permission.code.in_(wanted)))).all() if wanted else []
    found = {p.code for p in perms}
    missing = [code for code in wanted if code not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Тодорхойгүй эрхийн код: {', '.join(missing)}",
        )

    role.permissions.clear()
    await db.flush()
    for perm in perms:
        role.permissions.append(RolePermission(role_id=role.id, permission_id=perm.id))
    await db.flush()

    after_codes = sorted(found)
    await audit(
        db,
        user_id=current.id,
        action="role.permissions.update",
        entity_type="role",
        entity_id=role.id,
        before={"code": role.code, "permissions": ",".join(before_codes)},
        after={"code": role.code, "permissions": ",".join(after_codes)},
        ip=_client_ip(request),
    )

    user_count = int(
        (
            await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role_id == role.id, User.is_active.is_(True))
            )
        )
        or 0
    )
    return RoleOut(
        id=role.id,
        code=role.code,
        name_mn=_role_name(role),
        permissions=after_codes,
        user_count=user_count,
    )
