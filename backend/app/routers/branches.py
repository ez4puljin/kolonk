"""Салбар — жагсаах, үүсгэх, засах.

Шинэ салбар үүсгэх, засахыг **зөвхөн эзэн** (`settings.manage`) хийнэ.
Жагсаалтыг нэвтэрсэн бүх хэрэглэгч харна — түгээгчийн харьяа салбарыг харуулахад
болон тайлангийн шүүлтэд хэрэгтэй.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.branch import Branch
from app.models.shift import Shift
from app.models.user import User
from app.services import branch_payment_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["branches"])

CanManage = Depends(require_permission("settings.manage"))


class BranchIn(BaseModel):
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    is_active: bool = True
    sort_order: int = 0


class BranchUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PaymentMethodRow(BaseModel):
    """Салбарын нэг төлбөрийн хэрэгсэл."""

    method: str
    label: str = ""
    is_enabled: bool = True
    sort_order: int = 0
    #: Бэлэн мөнгө — хаах боломжгүй (хариулт, ээлжийн кассад шаардлагатай).
    locked: bool = False


class PaymentMethodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    is_enabled: bool = True


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    is_active: bool = True
    sort_order: int = 0
    #: Тухайн салбарт хэдэн хэрэглэгч харьяалагдаж байна.
    user_count: int = 0
    #: Ээлж нээгдсэн эсэх — салбар идэвхгүй болгохын өмнө шалгана.
    open_shifts: int = 0


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


async def _with_counts(db: AsyncSession, rows: list[Branch]) -> list[BranchOut]:
    ids = [b.id for b in rows]
    users: dict[uuid.UUID, int] = {}
    shifts: dict[uuid.UUID, int] = {}
    if ids:
        for bid, count in (
            await db.execute(
                select(User.branch_id, func.count(User.id))
                .where(User.branch_id.in_(ids), User.is_active.is_(True))
                .group_by(User.branch_id)
            )
        ).all():
            users[bid] = count
        for bid, count in (
            await db.execute(
                select(Shift.branch_id, func.count(Shift.id))
                .where(Shift.branch_id.in_(ids), Shift.status == "open")
                .group_by(Shift.branch_id)
            )
        ).all():
            shifts[bid] = count

    return [
        BranchOut(
            id=b.id,
            code=b.code,
            name=b.name,
            address=b.address,
            phone=b.phone,
            is_active=b.is_active,
            sort_order=b.sort_order,
            user_count=users.get(b.id, 0),
            open_shifts=shifts.get(b.id, 0),
        )
        for b in rows
    ]


@router.get("/branches", response_model=list[BranchOut])
async def list_branches(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (await db.scalars(select(Branch).order_by(Branch.sort_order, Branch.name))).all()
    return await _with_counts(db, list(rows))


@router.post("/branches", response_model=BranchOut, status_code=201)
async def create_branch(
    payload: BranchIn,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    code = _clean(payload.code)
    name = _clean(payload.name)
    if not code or not name:
        raise HTTPException(status_code=422, detail="Салбарын код, нэр шаардлагатай")
    if await db.scalar(select(Branch).where(Branch.code == code)):
        raise HTTPException(status_code=422, detail="Ийм кодтой салбар бүртгэгдсэн байна")

    branch = Branch(
        code=code,
        name=name,
        address=_clean(payload.address),
        phone=_clean(payload.phone),
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(branch)
    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="branch.create",
        entity_type="branch",
        entity_id=branch.id,
        after={"code": branch.code, "name": branch.name},
    )
    return (await _with_counts(db, [branch]))[0]


@router.patch("/branches/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй")

    before = {"code": branch.code, "name": branch.name, "is_active": branch.is_active}

    if payload.code is not None:
        code = _clean(payload.code)
        if code and code != branch.code:
            if await db.scalar(select(Branch).where(Branch.code == code)):
                raise HTTPException(status_code=422, detail="Ийм кодтой салбар бүртгэгдсэн байна")
            branch.code = code
    if payload.name is not None:
        branch.name = _clean(payload.name) or branch.name
    if payload.address is not None:
        branch.address = _clean(payload.address)
    if payload.phone is not None:
        branch.phone = _clean(payload.phone)
    if payload.sort_order is not None:
        branch.sort_order = payload.sort_order

    if payload.is_active is not None and payload.is_active != branch.is_active:
        if not payload.is_active:
            # Нээлттэй ээлжтэй эсвэл ажилтантай салбарыг хаахыг зөвшөөрөхгүй.
            open_shifts = await db.scalar(
                select(func.count(Shift.id)).where(
                    Shift.branch_id == branch.id, Shift.status == "open"
                )
            )
            if open_shifts:
                raise HTTPException(
                    status_code=422, detail="Нээлттэй ээлжтэй салбарыг идэвхгүй болгох боломжгүй"
                )
            staff = await db.scalar(
                select(func.count(User.id)).where(
                    User.branch_id == branch.id, User.is_active.is_(True)
                )
            )
            if staff:
                raise HTTPException(
                    status_code=422,
                    detail=f"{staff} идэвхтэй ажилтан харьяалагдаж байна — эхлээд шилжүүлнэ үү",
                )
        branch.is_active = payload.is_active

    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="branch.update",
        entity_type="branch",
        entity_id=branch.id,
        before=before,
        after={"code": branch.code, "name": branch.name, "is_active": branch.is_active},
    )
    return (await _with_counts(db, [branch]))[0]


# --------------------------------------------------------------------------- #
# Төлбөрийн хэлбэр
# --------------------------------------------------------------------------- #
async def _branch_or_404(db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй")
    return branch


@router.get("/branches/{branch_id}/payment-methods", response_model=list[PaymentMethodRow])
async def list_branch_payment_methods(
    branch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[PaymentMethodRow]:
    """Салбарын төлбөрийн хэрэгслүүд. Тохируулаагүй бол бүгд идэвхтэй."""
    await _branch_or_404(db, branch_id)
    rows = await branch_payment_service.list_methods(db, branch_id)
    return [PaymentMethodRow(**row) for row in rows]


@router.put("/branches/{branch_id}/payment-methods", response_model=list[PaymentMethodRow])
async def set_branch_payment_methods(
    branch_id: uuid.UUID,
    payload: list[PaymentMethodIn],
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> list[PaymentMethodRow]:
    """Салбарын төлбөрийн хэрэгслийг бүхэлд нь тохируулна (зөвхөн эзэн)."""
    branch = await _branch_or_404(db, branch_id)
    before = await branch_payment_service.list_methods(db, branch_id)
    rows = await branch_payment_service.set_methods(db, branch_id, payload)

    await audit(
        db,
        user_id=user.id,
        action="branch.payment_methods",
        entity_type="branch",
        entity_id=branch.id,
        before={"methods": [r["method"] for r in before if r["is_enabled"]]},
        after={"methods": [r["method"] for r in rows if r["is_enabled"]]},
    )
    return [PaymentMethodRow(**row) for row in rows]
