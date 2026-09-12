"""Нэвтрэлт — салбар сонгож нэвтрэх, ПИН, ажлын салбар солих, гарах.

Урсгал: нэвтрэх дэлгэц эхлээд САЛБАР сонгуулна (`/auth/branches`), дараа нь
тэр салбарын хэрэглэгчийг (`/auth/users`), эцэст нь ПИН (`/auth/login`,
``branch_id``-тай). Админ салбаргүй тусдаа нэвтэрч админ панел руу очно.

Сонгосон салбар токены ``bid`` claim-д хадгалагдана; серверийн салбарын
логик (`branch_service.effective_branch_id`) түгээгчийн харьяа салбарыг
эхэнд, дараа нь энэ claim-ыг харна.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, user_permissions
from app.enums import RoleCode, ShiftStatus
from app.models.branch import Branch
from app.models.shift import Shift
from app.models.user import User
from app.permissions import ROLE_NAMES_MN
from app.schemas.auth import (
    BranchInfo,
    LoginBranch,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SwitchBranchRequest,
    UserTile,
)
from app.schemas.system import OkResponse
from app.security import create_token, verify_pin
from app.services import login_guard_service
from app.services.audit_service import audit
from app.services.branch_service import effective_branch_id

router = APIRouter(prefix="/api", tags=["auth"])

BAD_PIN = "ПИН код буруу байна"


def _client_ip(request: Request) -> str | None:
    """Хэрэглэгчийн жинхэнэ IP.

    ``CF-Connecting-IP``-г эхэнд харна: Cloudflare Tunnel-ээр орж ирэхэд
    үүнийг өөрөө тавьдаг бөгөөд хэрэглэгчийн илгээсэн хуурамч утгыг
    дарж бичдэг. ``X-Forwarded-For`` бол зөвхөн орон нутгийн nginx-ийн
    ард ажиллах үеийн нөөц хувилбар.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


#: Эдгээр дүр бүх салбарыг хардаг — салбарын хязгаарлалтгүй.
ALL_BRANCH_ROLES = {str(RoleCode.MANAGER), str(RoleCode.OWNER)}


def _sees_all(user: User) -> bool:
    return str(user.role.code) in ALL_BRANCH_ROLES


def _tile(user: User, branch: Branch | None = None) -> UserTile:
    role = user.role
    return UserTile(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        role_code=role.code,
        role_name_mn=role.name_mn or ROLE_NAMES_MN.get(role.code, role.code),
        branch=(
            BranchInfo(id=branch.id, code=branch.code, name=branch.name) if branch else None
        ),
        # Түгээгчийн салбар санд хатуу заагдсан — солигдохгүй.
        branch_locked=user.branch_id is not None,
        all_branches=_sees_all(user),
    )


async def _working_branch(db: AsyncSession, user: User) -> Branch | None:
    """Хэрэглэгчийн ажлын салбар: харьяа салбар → нэвтрэхдээ сонгосон → None."""
    branch_id = effective_branch_id(user)
    if branch_id is None:
        return None
    return await db.get(Branch, branch_id)


async def _active_branch_or_422(db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=422, detail="Салбар олдсонгүй эсвэл идэвхгүй байна")
    return branch


async def _open_shift(db: AsyncSession, branch_id: uuid.UUID | None = None) -> Shift | None:
    stmt = select(Shift).where(Shift.status == ShiftStatus.OPEN)
    if branch_id is not None:
        stmt = stmt.where(Shift.branch_id == branch_id)
    return await db.scalar(stmt.order_by(Shift.opened_at.desc()).limit(1))


# --------------------------------------------------------------------------- #
# Нэвтрэх дэлгэцийн нээлттэй өгөгдөл
# --------------------------------------------------------------------------- #
@router.get("/auth/branches", response_model=list[LoginBranch])
async def login_branches(db: AsyncSession = Depends(get_db)) -> list[LoginBranch]:
    """Нэвтрэх дэлгэцийн салбарын хайрцгууд (нэвтрэх шаардлагагүй).

    Идэвхтэй салбарууд, тус бүрд одоо ээлж нээлттэй бол хэн нээснийг,
    ажилтны тоог хамт өгнө — ажилдаа ирж буй хүн нэг харцаар ойлгоно.
    """
    branches = (
        await db.scalars(
            select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.sort_order, Branch.name)
        )
    ).all()
    if not branches:
        return []
    ids = [b.id for b in branches]

    staff: dict[uuid.UUID, int] = {
        bid: count
        for bid, count in (
            await db.execute(
                select(User.branch_id, func.count(User.id))
                .where(User.branch_id.in_(ids), User.is_active.is_(True))
                .group_by(User.branch_id)
            )
        ).all()
    }

    open_by: dict[uuid.UUID, str] = {}
    rows = (
        await db.execute(
            select(Shift.branch_id, User.full_name)
            .join(User, User.id == Shift.opened_by)
            .where(Shift.status == ShiftStatus.OPEN, Shift.branch_id.in_(ids))
            .order_by(Shift.opened_at.desc())
        )
    ).all()
    for bid, name in rows:
        open_by.setdefault(bid, name)

    return [
        LoginBranch(
            id=b.id,
            code=b.code,
            name=b.name,
            address=b.address,
            open_shift_by=open_by.get(b.id),
            staff_count=staff.get(b.id, 0),
        )
        for b in branches
    ]


@router.get("/auth/users", response_model=list[UserTile])
async def login_tiles(db: AsyncSession = Depends(get_db)) -> list[UserTile]:
    """Нэвтрэх дэлгэцэд харагдах идэвхтэй хэрэглэгчид (нэвтрэх шаардлагагүй).

    Салбар нь хайрцаг дээр гарна: нэвтрэх дэлгэц сонгосон салбарын
    түгээгчид + салбаргүй нягтланг үзүүлж, админыг тусад нь харуулна.
    """
    users = (
        await db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name))
    ).all()

    # Салбаруудыг нэг дор уншина — хэрэглэгч тутамд асуулга явуулахгүй.
    branch_ids = {u.branch_id for u in users if u.branch_id is not None}
    branches = (
        {b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()}
        if branch_ids
        else {}
    )
    return [_tile(u, branches.get(u.branch_id) if u.branch_id else None) for u in users]


# --------------------------------------------------------------------------- #
# Нэвтрэх / салбар солих / гарах
# --------------------------------------------------------------------------- #
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    # ПИН таах халдлагаас хамгаална — систем интернэтэд гарсан тул
    # хязгааргүй оролдлого бол 4-6 оронтой код хэдхэн минутад тайлагдана.
    ip = _client_ip(request)
    await login_guard_service.check_allowed(payload.user_id, ip)

    user = await db.scalar(select(User).where(User.id == payload.user_id))
    if user is None or not user.is_active or not verify_pin(payload.pin, user.pin_hash):
        await login_guard_service.record_failure(payload.user_id, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=BAD_PIN)

    # --- Салбар ---
    # Түгээгч: салбар нь санд байгаа — өөр салбараас нэвтрэхийг хориглоно
    # (нэг салбарын ээлж, касс нөгөөд бичигдэхээс сэргийлнэ).
    # Салбаргүй (нягтлан, админ): сонгосон салбар токенд орж ажлын салбар болно.
    token_branch: uuid.UUID | None = None
    if user.branch_id is not None:
        if payload.branch_id is not None and payload.branch_id != user.branch_id:
            own = await db.get(Branch, user.branch_id)
            raise HTTPException(
                status_code=422,
                # Салбарын нэрэнд ихэвчлэн «салбар» гэдэг үг орсон байдаг тул
                # «... салбар салбарт» гэж давхардуулахгүй.
                detail=f"{user.full_name} нь «{own.name if own else 'өөр салбар'}»-т харьяалагддаг — тэр салбараас нэвтэрнэ үү",
            )
    elif payload.branch_id is not None:
        await _active_branch_or_422(db, payload.branch_id)
        token_branch = payload.branch_id
    user.active_branch_id = token_branch  # type: ignore[attr-defined]

    await login_guard_service.record_success(user.id, ip)
    user.last_login_at = datetime.now(UTC)
    await audit(
        db,
        user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        after={
            "username": user.username,
            "role": user.role.code,
            "branch_id": str(effective_branch_id(user)) if effective_branch_id(user) else None,
        },
        ip=ip,
    )

    return LoginResponse(
        token=create_token(user.id, user.role.code, token_branch),
        user=_tile(user, await _working_branch(db, user)),
        permissions=sorted(user_permissions(user)),
    )


@router.post("/auth/branch", response_model=LoginResponse)
async def switch_branch(
    payload: SwitchBranchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Ажлын салбараа солих — зөвхөн салбаргүй хэрэглэгч (нягтлан, админ).

    Шинэ токен буцаана: салбар токенд байдаг тул сесс дахин үүсэхгүйгээр
    солих боломжгүй. Түгээгчийн салбар хатуу тул 403.
    """
    if user.branch_id is not None or not _sees_all(user):
        raise HTTPException(status_code=403, detail="Таны салбар хатуу заагдсан — солих боломжгүй")
    if payload.branch_id is not None:
        await _active_branch_or_422(db, payload.branch_id)
    user.active_branch_id = payload.branch_id  # type: ignore[attr-defined]

    await audit(
        db,
        user_id=user.id,
        action="auth.switch_branch",
        entity_type="user",
        entity_id=user.id,
        after={"branch_id": str(payload.branch_id) if payload.branch_id else None},
        ip=_client_ip(request),
    )
    return LoginResponse(
        token=create_token(user.id, user.role.code, payload.branch_id),
        user=_tile(user, await _working_branch(db, user)),
        permissions=sorted(user_permissions(user)),
    )


@router.get("/auth/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    shift = await _open_shift(db, effective_branch_id(user))
    return MeResponse(
        user=_tile(user, await _working_branch(db, user)),
        permissions=sorted(user_permissions(user)),
        shift_open=shift is not None,
        shift_id=shift.id if shift else None,
        shift_number=shift.number if shift else None,
    )


@router.post("/auth/logout", response_model=OkResponse)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    await audit(
        db,
        user_id=user.id,
        action="auth.logout",
        entity_type="user",
        entity_id=user.id,
        ip=_client_ip(request),
    )
    return OkResponse()
