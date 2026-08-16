"""Харилцагчийн API (WP6).

Бүртгэл засварлахад ``contracts.manage`` эрх шаардана; ПОС дэлгэц харилцагч
хайх шаардлагатай тул **унших** үйлдэлд ``sales.create`` эрх ч хангалттай.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, inspect as sa_inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.money import q2
from app.stationtime import day_end, day_start
from app.deps import require_permission
from app.enums import CustomerType
from app.models.partner import Contract, Customer
from app.models.user import User
from app.schemas.partner import (
    ContractBrief,
    CustomerCreate,
    CustomerListOut,
    CustomerOut,
    CustomerUpdate,
)
from app.schemas.sale import OkOut
from app.services.audit_service import audit
from app.services.contract_service import CONTRACT_STATUS_MN, credit_available

router = APIRouter(prefix="/api", tags=["customers"])

CanManage = Depends(require_permission("contracts.manage"))
CanRead = Depends(require_permission("contracts.manage", "sales.create"))

#: Сканнердсан гэрээний PDF хадгалах хавтас (backend хавтастай харьцангуй).
CONTRACT_DIR = Path("uploads") / "customer_contracts"
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10MB

CUSTOMER_TYPE_MN: dict[str, str] = {
    CustomerType.B2B: "Байгууллага",
    CustomerType.INDIVIDUAL: "Иргэн",
}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _contract_brief(contract: Contract) -> ContractBrief:
    return ContractBrief(
        id=contract.id,
        contract_no=contract.contract_no,
        credit_limit=contract.credit_limit,
        balance=contract.balance,
        credit_available=credit_available(contract),
        price_discount_per_l=contract.price_discount_per_l,
        status=str(contract.status),
        status_name=CONTRACT_STATUS_MN.get(str(contract.status), str(contract.status)),
    )


def _loaded_contracts(customer: Customer) -> list[Contract]:
    """Ачаалагдсан гэрээнүүд. Шинэ бүртгэлд async lazy-load хийхээс сэргийлнэ."""
    if "contracts" in sa_inspect(customer).unloaded:
        return []
    return list(customer.contracts)


def _customer_out(customer: Customer) -> CustomerOut:
    full_name = (
        f"{customer.last_name} {customer.name}".strip() if customer.last_name else customer.name
    )
    return CustomerOut(
        id=customer.id,
        last_name=customer.last_name,
        name=customer.name,
        full_name=full_name,
        register_no=customer.register_no,
        phone=customer.phone,
        phone2=customer.phone2,
        email=customer.email,
        province=customer.province,
        district=customer.district,
        credit_limit=q2(customer.credit_limit or Decimal("0")),
        has_contract_file=bool(customer.contract_file),
        type=str(customer.type),
        type_name=CUSTOMER_TYPE_MN.get(str(customer.type), str(customer.type)),
        is_active=customer.is_active,
        contracts=[_contract_brief(c) for c in _loaded_contracts(customer)],
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def _snapshot(customer: Customer) -> dict:
    return {
        "last_name": customer.last_name,
        "name": customer.name,
        "register_no": customer.register_no,
        "phone": customer.phone,
        "phone2": customer.phone2,
        "email": customer.email,
        "province": customer.province,
        "district": customer.district,
        "credit_limit": str(customer.credit_limit or "0"),
        "contract_file": customer.contract_file,
        "type": str(customer.type),
        "is_active": customer.is_active,
    }


async def _load(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")
    return customer


@router.get("/customers", response_model=CustomerListOut)
async def list_customers(
    search: str | None = Query(default=None, description="Бүх мэдээллээр хайх"),
    type: CustomerType | None = Query(default=None),
    province: str | None = Query(default=None, description="Аймаг/хотоор шүүх"),
    district: str | None = Query(default=None, description="Сум/дүүргээр шүүх"),
    created_from: date | None = Query(default=None, description="Үүсгэсэн огноо (эхлэх)"),
    created_to: date | None = Query(default=None, description="Үүсгэсэн огноо (дуусах)"),
    active_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanRead,
) -> CustomerListOut:
    conditions: list = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Customer.name.ilike(pattern),
                Customer.last_name.ilike(pattern),
                Customer.register_no.ilike(pattern),
                Customer.phone.ilike(pattern),
                Customer.phone2.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.province.ilike(pattern),
                Customer.district.ilike(pattern),
            )
        )
    if type is not None:
        conditions.append(Customer.type == str(type))
    if province:
        conditions.append(Customer.province == province.strip())
    if district:
        conditions.append(Customer.district == district.strip())
    # Огноог станцын цагийн бүсээр тайлбарлана (CONTRACTS.md §1a).
    if created_from is not None:
        conditions.append(Customer.created_at >= day_start(created_from))
    if created_to is not None:
        conditions.append(Customer.created_at <= day_end(created_to))
    if active_only:
        conditions.append(Customer.is_active.is_(True))

    total = await db.scalar(select(func.count()).select_from(Customer).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Customer)
            .where(*conditions)
            .order_by(Customer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return CustomerListOut(items=[_customer_out(row) for row in rows], total=int(total))


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanRead,
) -> CustomerOut:
    return _customer_out(await _load(db, customer_id))


@router.post("/customers", response_model=CustomerOut, status_code=201)
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CustomerOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Харилцагчийн нэр хоосон байж болохгүй")

    register_no = (payload.register_no or "").strip() or None
    if register_no:
        clash = await db.scalar(
            select(func.count()).select_from(Customer).where(Customer.register_no == register_no)
        )
        if clash:
            raise HTTPException(status_code=422, detail="Ийм регистрийн дугаартай харилцагч бүртгэгдсэн байна")

    customer = Customer(
        last_name=(payload.last_name or "").strip() or None,
        name=name,
        register_no=register_no,
        phone=(payload.phone or "").strip() or None,
        phone2=(payload.phone2 or "").strip() or None,
        email=(payload.email or "").strip() or None,
        province=(payload.province or "").strip() or None,
        district=(payload.district or "").strip() or None,
        credit_limit=q2(payload.credit_limit or Decimal("0")),
        type=str(payload.type),
        is_active=payload.is_active,
    )
    db.add(customer)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="customer.create",
        entity_type="customer",
        entity_id=customer.id,
        after=_snapshot(customer),
        ip=_client_ip(request),
    )
    return _customer_out(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CustomerOut:
    customer = await _load(db, customer_id)
    before = _snapshot(customer)
    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Харилцагчийн нэр хоосон байж болохгүй")
        customer.name = name
    if "register_no" in changes:
        register_no = (changes["register_no"] or "").strip() or None
        if register_no and register_no != customer.register_no:
            clash = await db.scalar(
                select(func.count())
                .select_from(Customer)
                .where(Customer.register_no == register_no, Customer.id != customer.id)
            )
            if clash:
                raise HTTPException(
                    status_code=422, detail="Ийм регистрийн дугаартай харилцагч бүртгэгдсэн байна"
                )
        customer.register_no = register_no
    if "last_name" in changes:
        customer.last_name = (changes["last_name"] or "").strip() or None
    if "phone" in changes:
        customer.phone = (changes["phone"] or "").strip() or None
    if "phone2" in changes:
        customer.phone2 = (changes["phone2"] or "").strip() or None
    if "email" in changes:
        customer.email = (changes["email"] or "").strip() or None
    if "province" in changes:
        customer.province = (changes["province"] or "").strip() or None
    if "district" in changes:
        customer.district = (changes["district"] or "").strip() or None
    if "credit_limit" in changes and changes["credit_limit"] is not None:
        customer.credit_limit = q2(Decimal(str(changes["credit_limit"])))
    if "type" in changes and changes["type"] is not None:
        customer.type = str(changes["type"])
    if "is_active" in changes and changes["is_active"] is not None:
        customer.is_active = bool(changes["is_active"])

    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="customer.update",
        entity_type="customer",
        entity_id=customer.id,
        before=before,
        after=_snapshot(customer),
        ip=_client_ip(request),
    )
    return _customer_out(customer)


@router.delete("/customers/{customer_id}", response_model=OkOut)
async def deactivate_customer(
    customer_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> OkOut:
    """Түүх алдагдахаас сэргийлж устгахын оронд идэвхгүй болгоно."""
    customer = await _load(db, customer_id)
    if not customer.is_active:
        raise HTTPException(status_code=422, detail="Харилцагч аль хэдийн идэвхгүй байна")

    before = _snapshot(customer)
    customer.is_active = False
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="customer.deactivate",
        entity_type="customer",
        entity_id=customer.id,
        before=before,
        after=_snapshot(customer),
        ip=_client_ip(request),
    )
    return OkOut(ok=True, message="Харилцагчийг идэвхгүй болголоо")


# --------------------------------------------------------------------------- #
# Сканнердсан гэрээний PDF
# --------------------------------------------------------------------------- #
@router.post("/customers/{customer_id}/contract-file", response_model=CustomerOut)
async def upload_contract_file(
    customer_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CustomerOut:
    """Гэрээний сканнердсан PDF хавсаргана (заавал биш, 10MB хүртэл)."""
    customer = await _load(db, customer_id)

    content = await file.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=422, detail="Файл 10MB-аас хэтэрч байна")
    # Агуулгаар нь шалгана — өргөтгөлд итгэхгүй.
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Зөвхөн PDF файл хавсаргана")

    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{customer.id}.pdf"
    (CONTRACT_DIR / filename).write_bytes(content)

    before = _snapshot(customer)
    customer.contract_file = filename
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="customer.contract_file",
        entity_type="customer",
        entity_id=customer.id,
        before=before,
        after={"contract_file": filename, "size": len(content)},
        ip=_client_ip(request),
    )
    return _customer_out(customer)


@router.get("/customers/{customer_id}/contract-file")
async def download_contract_file(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanRead,
) -> FileResponse:
    customer = await _load(db, customer_id)
    if not customer.contract_file:
        raise HTTPException(status_code=404, detail="Гэрээний файл хавсаргаагүй байна")
    path = CONTRACT_DIR / customer.contract_file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Гэрээний файл олдсонгүй")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"geree-{customer.register_no or str(customer.id)[:8]}.pdf",
    )


@router.delete("/customers/{customer_id}/contract-file", response_model=CustomerOut)
async def delete_contract_file(
    customer_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CustomerOut:
    customer = await _load(db, customer_id)
    if not customer.contract_file:
        raise HTTPException(status_code=422, detail="Гэрээний файл хавсаргаагүй байна")

    before = _snapshot(customer)
    path = CONTRACT_DIR / customer.contract_file
    if path.is_file():
        path.unlink()
    customer.contract_file = None
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="customer.contract_file_delete",
        entity_type="customer",
        entity_id=customer.id,
        before=before,
        after={"contract_file": None},
        ip=_client_ip(request),
    )
    return _customer_out(customer)
