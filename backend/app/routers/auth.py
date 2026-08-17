"""Нэвтрэлт — нэвтрэх дэлгэцийн хэрэглэгчид, ПИН-ээр нэвтрэх, гарах."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, user_permissions
from app.enums import RoleCode, ShiftStatus
from app.models.shift import Shift
from app.models.branch import Branch
from app.models.user import User
from app.permissions import ROLE_NAMES_MN
from app.schemas.auth import (
    BranchInfo,
    LoginRequest,
    LoginResponse,
    MeResponse,
    UserTile,
)
from app.schemas.system import OkResponse
from app.security import create_token, verify_pin
from app.services import login_guard_service
from app.services.audit_service import audit

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
ALL_BRANCH_ROLES = {RoleCode.MANAGER, RoleCode.OWNER}


def _tile(user: User, branch: Branch | None = None) -> UserTile:
    role = user.role
    all_branches = str(role.code) in {str(r) for r in ALL_BRANCH_ROLES}
    return UserTile(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        role_code=role.code,
        role_name_mn=role.name_mn or ROLE_NAMES_MN.get(role.code, role.code),
        branch=(
            BranchInfo(id=branch.id, code=branch.code, name=branch.name) if branch else None
        ),
        all_branches=all_branches,
    )


async def _branch_of(db: AsyncSession, user: User) -> Branch | None:
    """Хэрэглэгчийн харьяа салбар. Менежер, эзэнд салбар хамаарахгүй."""
    if str(user.role.code) in {str(r) for r in ALL_BRANCH_ROLES}:
        return None
    if user.branch_id is None:
        return None
    return await db.get(Branch, user.branch_id)


async def _open_shift(db: AsyncSession) -> Shift | None:
    return await db.scalar(
        select(Shift).where(Shift.status == ShiftStatus.OPEN).order_by(Shift.opened_at.desc()).limit(1)
    )


@router.get("/auth/users", response_model=list[UserTile])
async def login_tiles(db: AsyncSession = Depends(get_db)) -> list[UserTile]:
    """Нэвтрэх дэлгэцэд харагдах идэвхтэй хэрэглэгчид (нэвтрэх шаардлагагүй).

    Салбар нь хайрцаг дээр гарна: нэг станцад олон салбарын түгээгч
    бүртгэлтэй үед зөвхөн нэрээр нь ялгахад төвөгтэй.
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
    return [
        _tile(
            u,
            None
            if str(u.role.code) in {str(r) for r in ALL_BRANCH_ROLES}
            else branches.get(u.branch_id),
        )
        for u in users
    ]


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

    await login_guard_service.record_success(user.id, ip)
    user.last_login_at = datetime.now(UTC)
    await audit(
        db,
        user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        after={"username": user.username, "role": user.role.code},
        ip=ip,
    )

    return LoginResponse(
        token=create_token(user.id, user.role.code),
        user=_tile(user, await _branch_of(db, user)),
        permissions=sorted(user_permissions(user)),
    )


@router.get("/auth/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    shift = await _open_shift(db)
    return MeResponse(
        user=_tile(user, await _branch_of(db, user)),
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
