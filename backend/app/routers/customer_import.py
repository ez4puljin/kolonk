"""Харилцагчийн Excel импорт — нэр, утас, авлага, огноо (4 багана).

Системд шилжихэд өмнөх авлагатай харилцагчдыг нэг файлаар оруулна:

* мөр бүр → харилцагч (утсаар, үгүй бол нэрээр таарвал шинээр үүсгэхгүй) +
  идэвхтэй гэрээ (байхгүй бол ``ИМ-YYYYMMDD-NN``);
* авлага > 0 бол гэрээний ``opening_balance``, ``balance``-д нэмэгдэж, тухайн
  огноогоор журналд Дт 1201 (харилцагчийн хэмжүүр) / Кт 3101 бичигдэнэ —
  тооцооны хуулгад «Эхний үлдэгдэл» мөрөөр гарна;
* зээлийн лимит хамгийн багадаа авлагатай тэнцүү болно (дараа нь засна).

Харилцагчийн сан бүх салбарт нийтлэг тул салбар заахгүй.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import ContractStatus, CustomerType, EventType, SourceType
from app.models.partner import Contract, Customer
from app.models.user import User
from app.money import q2
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.posting import Dims, LineSpec, posting

router = APIRouter(prefix="/api", tags=["customers"])

ZERO = Decimal("0")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


class ImportErrorRow(BaseModel):
    row: int
    message: str


class CustomerImportOut(BaseModel):
    rows: int
    customers_created: int
    customers_matched: int
    contracts_created: int
    receivable_total: Decimal
    errors: list[ImportErrorRow]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _phone(value: Any) -> str | None:
    raw = _text(value)
    digits = re.sub(r"[^\d+]", "", raw)
    return digits or None


def _amount(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, (int, float, Decimal)):
        return q2(Decimal(str(value)))
    raw = re.sub(r"[^\d.,-]", "", str(value)).replace(",", "")
    if raw in ("", "-", "."):
        return ZERO
    try:
        return q2(Decimal(raw))
    except InvalidOperation as exc:
        raise ValueError(f"Авлагын дүн танигдсангүй: {value!r}") from exc


_DATE_FORMATS = ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d")


def _date(value: Any, fallback: date) -> date:
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Огноо танигдсангүй: {raw!r} (жишээ: 2026-09-13)")


_HEADER_WORDS = {"нэр", "name", "харилцагч", "customer"}


def _looks_like_header(row: tuple[Any, ...]) -> bool:
    """Эхний мөр гарчиг уу — нэрийн багана «Нэр» г.м., эсвэл авлага/огнооны
    багана тоогүй текст бол гарчиг гэж үзнэ."""
    first = _text(row[0] if row else None).lower()
    if first in _HEADER_WORDS:
        return True
    for cell in row[2:4]:
        if isinstance(cell, str) and cell.strip() and not re.search(r"\d", cell):
            return True
    return False


async def _next_contract_no(db: AsyncSession, prefix: str) -> str:
    count = await db.scalar(
        select(func.count()).select_from(Contract).where(Contract.contract_no.like(f"{prefix}-%"))
    )
    seq = int(count or 0) + 1
    while True:
        candidate = f"{prefix}-{seq:03d}"
        clash = await db.scalar(
            select(func.count()).select_from(Contract).where(Contract.contract_no == candidate)
        )
        if not clash:
            return candidate
        seq += 1


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _build_template() -> bytes:
    """Импортын загвар: гарчиг + 2 жишээ мөр, тайлбар хуудастай."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Харилцагч"
    ws.append(["Нэр", "Утас", "Авлага", "Огноо"])
    ws.append(["Бат-Эрдэнэ", "99112233", 150000, date(2026, 8, 31)])
    ws.append(["Оюунаа", "88445566", 0, None])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DBEAFE")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 14
    ws["D2"].number_format = "yyyy-mm-dd"
    ws["C2"].number_format = "#,##0"

    notes = wb.create_sheet("Тайлбар")
    for line in (
        "A — Нэр: заавал. Овог нэрийг нэг нүдэнд бичиж болно.",
        "B — Утас: сонголтоор. Ижил утастай мөрүүд нэг харилцагчид нэгтгэгдэнэ;",
        "    бүртгэлтэй харилцагчтай таарвал шинээр үүсгэхгүй.",
        "C — Авлага (₮): тухайн харилцагчийн танд төлөх өр. 0 эсвэл хоосон бол зөвхөн харилцагч + гэрээ үүснэ.",
        "D — Огноо: авлага үүссэн огноо (2026-09-13, 2026.09.13, 13.09.2026 эсвэл Excel огноо). Хоосон бол өнөөдөр.",
        "",
        "Эхний «Харилцагч» хуудсыг л уншина; гарчгийн мөрийг устгахгүй байж болно.",
        "Авлага гэрээний эхний үлдэгдэл болж, журналд Дт 1201 / Кт 3101 бичигдэнэ;",
        "зээлийн лимит авлагатай тэнцүү тогтоно — дараа нь Харилцагч → Гэрээ хэсгээс засна.",
    ):
        notes.append([line])
    notes.column_dimensions["A"].width = 110

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@router.get("/customers/import-template")
async def import_template(
    _user: User = Depends(require_permission("contracts.manage")),
) -> StreamingResponse:
    """Импортын Excel загвар (нэр, утас, авлага, огноо) татах."""
    payload = _build_template()
    return StreamingResponse(
        BytesIO(payload),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=\"customer-import-template.xlsx\""},
    )


@router.post("/customers/import", response_model=CustomerImportOut, status_code=201)
async def import_customers(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("contracts.manage")),
) -> CustomerImportOut:
    """Excel (.xlsx): A=нэр, B=утас, C=авлага, D=огноо. Эхний мөр гарчиг байж болно."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Файл хоосон байна")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="Файл 5MB-аас хэтэрч байна")

    try:
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — openpyxl олон төрлийн алдаа өгдөг
        raise HTTPException(status_code=422, detail="Excel (.xlsx) файл уншиж чадсангүй") from exc

    sheet = workbook.worksheets[0]
    rows = [tuple(r) for r in sheet.iter_rows(values_only=True)]
    workbook.close()
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    if not rows:
        raise HTTPException(status_code=422, detail="Файлд мөр алга")
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=422, detail=f"Нэг удаад {MAX_ROWS} мөр хүртэл")

    start_index = 1 if _looks_like_header(rows[0]) else 0
    today = datetime.now(UTC).date()
    stamp = f"ИМ-{today:%Y%m%d}"

    created = matched = contracts_created = 0
    receivable_total = ZERO
    errors: list[ImportErrorRow] = []
    processed = 0
    # Нэг файл дотор ижил утас/нэр давтагдвал нэг л харилцагч.
    seen: dict[str, Customer] = {}

    for index, row in enumerate(rows[start_index:], start=start_index + 1):
        cells = list(row) + [None] * 4
        name = _text(cells[0])
        if not name:
            errors.append(ImportErrorRow(row=index, message="Нэр хоосон"))
            continue
        try:
            phone = _phone(cells[1])
            amount = _amount(cells[2])
            as_of = _date(cells[3], today)
        except ValueError as exc:
            errors.append(ImportErrorRow(row=index, message=str(exc)))
            continue
        if amount < ZERO:
            errors.append(ImportErrorRow(row=index, message="Авлага сөрөг байж болохгүй"))
            continue

        key = phone or name.lower()
        customer = seen.get(key)
        if customer is not None:
            # Нэг файлд давтагдсан харилцагч — авлага нь нэг гэрээнд нэмэгдэнэ.
            matched += 1
        if customer is None:
            if phone:
                customer = await db.scalar(
                    select(Customer).where(Customer.phone == phone, Customer.is_active.is_(True))
                )
            if customer is None:
                customer = await db.scalar(
                    select(Customer).where(func.lower(Customer.name) == name.lower(), Customer.is_active.is_(True))
                )
            if customer is None:
                customer = Customer(
                    name=name,
                    phone=phone,
                    credit_limit=amount,
                    credit_unlimited=True,
                    type=str(CustomerType.INDIVIDUAL),
                    is_active=True,
                )
                db.add(customer)
                await db.flush()
                created += 1
            else:
                matched += 1
                if phone and not customer.phone:
                    customer.phone = phone
            seen[key] = customer

        contract = await db.scalar(
            select(Contract)
            .where(Contract.customer_id == customer.id, Contract.status == str(ContractStatus.ACTIVE))
            .order_by(Contract.created_at)
        )
        if contract is None:
            contract = Contract(
                customer=customer,
                contract_no=await _next_contract_no(db, stamp),
                credit_limit=amount,
                balance=ZERO,
                price_discount_per_l=ZERO,
                billing_day=1,
                status=str(ContractStatus.ACTIVE),
            )
            db.add(contract)
            await db.flush()
            contracts_created += 1

        if amount > ZERO:
            contract.opening_balance = q2(Decimal(contract.opening_balance or ZERO) + amount)
            contract.opening_date = as_of if contract.opening_date is None else min(contract.opening_date, as_of)
            contract.balance = q2(Decimal(contract.balance or ZERO) + amount)
            if q2(Decimal(contract.credit_limit or ZERO)) < q2(Decimal(contract.balance)):
                contract.credit_limit = q2(Decimal(contract.balance))
            if q2(Decimal(customer.credit_limit or ZERO)) < q2(Decimal(contract.credit_limit)):
                customer.credit_limit = q2(Decimal(contract.credit_limit))
            memo = f"Авлагын эхний үлдэгдэл — {customer.name} ({contract.contract_no})"
            await posting.post(
                db,
                event_type=str(EventType.OPENING_BALANCE_POSTED),
                source_type=str(SourceType.OPENING_BALANCE),
                source_id=uuid.uuid4(),
                entry_date=as_of,
                description=memo[:255],
                lines=[
                    LineSpec(
                        account_code=ACC.AR_CONTRACT,
                        debit=amount,
                        memo=memo[:255],
                        dims=Dims(customer_id=customer.id),
                    ),
                    LineSpec(account_code=ACC.OWNER_CAPITAL, credit=amount, memo=memo[:255]),
                ],
                posted_by=user.id,
            )
            receivable_total = q2(receivable_total + amount)
        processed += 1

    if processed == 0:
        raise HTTPException(
            status_code=422,
            detail="Нэг ч мөр импортлогдсонгүй: " + "; ".join(f"{e.row}-р мөр: {e.message}" for e in errors[:5]),
        )

    await audit(
        db,
        user_id=user.id,
        action="customer.import",
        entity_type="customer",
        entity_id=user.id,
        after={
            "file": (file.filename or "")[:120],
            "rows": processed,
            "created": created,
            "matched": matched,
            "contracts": contracts_created,
            "receivable_total": str(receivable_total),
            "errors": len(errors),
        },
        ip=_client_ip(request),
    )
    return CustomerImportOut(
        rows=processed,
        customers_created=created,
        customers_matched=matched,
        contracts_created=contracts_created,
        receivable_total=receivable_total,
        errors=errors,
    )
