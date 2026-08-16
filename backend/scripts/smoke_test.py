"""End-to-end шалгалт — бүх бизнес урсгалыг дараалуулан гүйцэтгэнэ.

Ажиллуулах (API асаалттай байхад):

    python backend/scripts/smoke_test.py [http://localhost:8000]

Шалгах зүйл: нэвтрэх/эрх → ээлж нээх → насос authorize + амьд таталт →
бэлэн/хуваасан/гэрээт/ваучер/картын төлбөр → бараа зарах → таталт бүртгэх →
худалдан авалт → өглөгийн төлбөр → нэхэмжлэх/авлагын төлбөр → буцаалт батлах →
үнэ өөрчлөх → ээлж хаах (зөрүүтэй) → тайлан/Excel → НББ-ийн бүрэн бүтэн байдал.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from decimal import Decimal

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

# seed.py-ийн DEMO_PIN-тэй тохирно. Өөр ПИН тохируулсан бол:
#   python -m scripts.smoke_test http://localhost:8000 <ПИН>
DEMO_PIN = sys.argv[2] if len(sys.argv) > 2 else "000000"
PINS = {"owner": DEMO_PIN, "manager": DEMO_PIN, "cashier": DEMO_PIN}

OK, BAD = "✓", "✗"
_token: str | None = None
_results: list[tuple[bool, str, str]] = []


# --------------------------------------------------------------------------- #
# HTTP туслах
# --------------------------------------------------------------------------- #
def call(path: str, data=None, method: str | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method or "GET")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)[:400]


def post(path: str, data=None):
    """POST — биегүй байсан ч заавал POST-оор явуулна."""
    return call(path, data if data is not None else {}, method="POST")


def download(path: str) -> tuple[int, bytes]:
    req = urllib.request.Request(BASE + path)
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


def upload_file(path: str, content: bytes, filename: str):
    """Multipart файл илгээх (банкны хуулга)."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)[:400]


def _demo_statement(account_number: str) -> bytes:
    """Хаанбанкны хуулгатай ижил бүтэцтэй туршилтын Excel (санах ойд)."""
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Хэвлэсэн: 2026/08/12", None, f"Данс: {account_number}", None,
               "Интервал: 2026/08/01 - 2026/08/05"])
    ws.append(["Гүйлгээний огноо", "Салбар", "Валют", "Дебит", "Кредит", "Үлдэгдэл",
               "Гүйлгээний утга", "Харьцсан данс"])
    demo = [
        (datetime(2026, 8, 1), 0, 1_200_000, "POS SETTLEMENT 2026/08/01", 5303363476.0),
        (datetime(2026, 8, 2), 0, 800_000, "Харилцагчийн шилжүүлэг", 5301111111.0),
        (datetime(2026, 8, 3), 700_000, 0, "Цахилгааны төлбөр", 5302222222.0),
        (datetime(2026, 8, 4), 3_000, 0, "Гүйлгээний хураамж", None),
        (datetime(2026, 8, 5), 2_000, 0, "Гүйлгээний хураамж", None),
    ]
    for when, debit, credit, desc, counterpart in demo:
        ws.append([when, "Төв", "MNT", debit, credit, 0, desc, counterpart])
    ws.append(["Нийт дүн:", None, None, 705_000, 2_000_000, None, None, None])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def rows(payload):
    return payload["items"] if isinstance(payload, dict) and "items" in payload else payload


def check(label: str, ok: bool, detail: str = "") -> bool:
    _results.append((ok, label, detail))
    print(f"{OK if ok else BAD} {label}" + (f"\n      {detail[:300]}" if not ok and detail else ""))
    return ok


def expect(label: str, status: int, body, codes=(200, 201)):
    return check(label, status in codes, str(body))


def login(role: str) -> dict | None:
    global _token
    s, users = call("/api/auth/users")
    if s != 200:
        check(f"нэвтрэх ({role})", False, str(users))
        return None
    user = next((u for u in users if u["role_code"] == role), None)
    if user is None:
        check(f"нэвтрэх ({role})", False, f"{role} хэрэглэгч алга")
        return None
    s, lg = post("/api/auth/login", {"user_id": user["id"], "pin": PINS[role]})
    if not expect(f"нэвтрэх — {user['full_name']} ({role})", s, lg):
        return None
    _token = lg["token"]
    return lg


def d(v) -> Decimal:
    return Decimal(str(v))


# --------------------------------------------------------------------------- #
def main() -> int:
    global _token
    print(f"\n{'=' * 66}\n  Колонк ШТС — end-to-end шалгалт\n  {BASE}\n{'=' * 66}")

    # ---- Эрүүл мэнд ------------------------------------------------------ #
    print("\n── СИСТЕМ ──")
    s, h = call("/api/health")
    if not expect("health", s, h):
        print("\nAPI хариу өгөхгүй байна. Эхлээд сервер асаана уу.")
        return 1
    check("  өгөгдлийн сан + Redis", bool(h.get("db") and h.get("redis")), json.dumps(h))

    # ---- Нэвтрэх, эрх ---------------------------------------------------- #
    print("\n── НЭВТРЭХ, ЭРХ ──")
    if not login("cashier"):
        return 1
    s, bad = post("/api/auth/login", {"user_id": rows(call("/api/auth/users")[1])[0]["id"], "pin": "0000"})
    check("буруу ПИН татгалзсан", s == 401, str(bad))
    s, me = call("/api/auth/me")
    expect("өөрийн мэдээлэл", s, me)
    s, denied = call("/api/audit-logs")
    check("кассчин аудит лог үзэх боломжгүй", denied and s == 403, str(denied))

    # ---- Ээлж нээх ------------------------------------------------------- #
    print("\n── ЭЭЛЖ НЭЭХ ──")
    _token and None
    s, cur = call("/api/shifts/current")
    if cur:
        shift = cur.get("shift", cur)
        print(f"  (нээлттэй ээлж №{shift['number']} байна — үүнийг ашиглана)")
    else:
        _, tanks = call("/api/tanks")
        _, pumps = call("/api/pumps")
        nozzles = [n for p in rows(pumps) for n in p["nozzles"]]
        s, res = post("/api/shifts/open", {
            "opening_cash": "500000.00",
            "tank_dips": [{"tank_id": t["id"], "dip_liters": t["current_l"]} for t in rows(tanks)],
            "totalizer_readings": [{"nozzle_id": n["id"], "reading": n["totalizer"]} for n in nozzles],
        })
        if not expect("ээлж нээв", s, res):
            return 1
        shift = res.get("shift", res)
    print(f"  ээлж №{shift['number']}, эхний касс {shift['opening_cash']}₮")

    # ---- Насосны таталт --------------------------------------------------- #
    print("\n── НАСОСНЫ ТАТАЛТ ──")
    _, pumps = call("/api/pumps")
    pump = rows(pumps)[0]
    nozzle = pump["nozzles"][0]
    _, fuel_list = call("/api/fuels")
    fuel_rec = next(x for x in rows(fuel_list) if x["id"] == nozzle["fuel_id"])
    price = d(fuel_rec["price_per_liter"])
    s, auth = post(f"/api/pumps/{pump['id']}/authorize",
                   {"nozzle_id": nozzle["id"], "preset_type": "liters", "preset_value": "20"})
    auth_id = auth.get("authorization_id") if expect(f"насос №{pump['number']} authorize (20л)", s, auth) else None

    if auth_id:
        status, live = "authorized", {}
        for _ in range(60):
            time.sleep(1)
            _, snap = call("/api/pumps")
            cur_pump = next(x for x in rows(snap) if x["id"] == pump["id"])
            status = cur_pump["status"]
            live = cur_pump.get("live") or live
            if status in ("idle", "complete"):
                break
        check(f"таталт дууссан ({live.get('liters')} л = {live.get('amount')} ₮)",
              status in ("idle", "complete"), f"төлөв={status}")

    # ---- Борлуулалт ------------------------------------------------------- #
    print("\n── БОРЛУУЛАЛТ ──")
    amount = (price * 20).quantize(Decimal("0.01"))
    received = ((amount // 1000) + 1) * 1000
    s, sale1 = post("/api/sales", {
        "sale_type": "fuel",
        "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"],
                   "pump_id": pump["id"], "nozzle_id": nozzle["id"], "qty": "20.000",
                   "authorization_id": auth_id}],
        "payments": [{"method": "cash", "amount": str(amount), "received": str(received)}],
    })
    expect(f"түлш бэлнээр ({amount}₮, хариулт {received - amount}₮)", s, sale1)

    half = (amount / 2).quantize(Decimal("0.01"))
    s, r = post("/api/sales", {
        "sale_type": "fuel",
        "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"], "qty": "20.000"}],
        "payments": [{"method": "card", "amount": str(half), "ref_no": "SLIP-1"},
                     {"method": "qr", "amount": str(amount - half), "ref_no": "QR-1"}],
    })
    expect("хуваасан төлбөр (карт + QR)", s, r)

    s, r = post("/api/sales", {
        "sale_type": "fuel",
        "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"], "qty": "20.000"}],
        "payments": [{"method": "cash", "amount": "100.00", "received": "100.00"}],
    })
    check("дутуу төлбөр татгалзсан", s == 422, str(r))

    _, prods = call("/api/products?limit=3")
    p1 = rows(prods)[0]
    tot = (d(p1["price"]) * 2).quantize(Decimal("0.01"))
    stock_before = d(p1["stock_qty"])
    s, r = post("/api/sales", {
        "sale_type": "store",
        "items": [{"item_type": "product", "product_id": p1["id"], "qty": "2"}],
        "payments": [{"method": "cash", "amount": str(tot), "received": str(tot)}],
    })
    if expect(f"бараа зарав ({p1['name_mn']} ×2 = {tot}₮)", s, r):
        _, again = call(f"/api/products/{p1['id']}")
        check("барааны үлдэгдэл хасагдсан", d(again["stock_qty"]) == stock_before - 2,
              f"{stock_before} → {again['stock_qty']}")

    # гэрээт (хөнгөлөлт тооцно)
    s, cts = call("/api/contracts")
    if s == 200 and rows(cts):
        ct = rows(cts)[0]
        eff = price - d(ct.get("price_discount_per_l") or 0)
        camt = (eff * 50).quantize(Decimal("0.01"))
        s, r = post("/api/sales", {
            "sale_type": "fuel",
            "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"], "qty": "50.000"}],
            "payments": [{"method": "contract", "amount": str(camt), "contract_id": ct["id"]}],
            "contract_id": ct["id"], "customer_id": ct["customer_id"],
        })
        expect(f"гэрээт борлуулалт {ct['contract_no']} (50л × {eff}₮)", s, r)
        huge = (eff * 100000).quantize(Decimal("0.01"))
        s, r = post("/api/sales", {
            "sale_type": "fuel",
            "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"], "qty": "100000.000"}],
            "payments": [{"method": "contract", "amount": str(huge), "contract_id": ct["id"]}],
            "contract_id": ct["id"], "customer_id": ct["customer_id"],
        })
        check("кредит лимит хамгаалсан", s == 422 and "лимит" in str(r).lower(), str(r))

    # ---- Түлш + бараа нэг борлуулалтад -------------------------------------- #
    print("\n── ХОЛИМОГ БОРЛУУЛАЛТ (түлш + бараа) ──")
    _, prod_list = call("/api/products?limit=5")
    mix_product = next((p for p in rows(prod_list) if p["is_active"] and d(p["stock_qty"]) > 2), None)
    if mix_product:
        fuel_amt = (price * 10).quantize(Decimal("0.01"))
        prod_amt = d(mix_product["price"])
        mix_total = fuel_amt + prod_amt
        s, mixed = post("/api/sales", {
            "sale_type": "mixed",
            "items": [
                {"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"],
                 "nozzle_id": nozzle["id"], "qty": "10", "unit_price": str(price)},
                {"item_type": "product", "product_id": mix_product["id"], "qty": "1",
                 "unit_price": str(prod_amt)},
            ],
            "payments": [{"method": "cash", "amount": str(mix_total), "received": str(mix_total)}],
        })
        if expect("түлш + бараа нэг баримтад", s, mixed):
            head = mixed.get("sale", mixed)
            check(f"  төрөл = mixed ({head['sale_type']})", head["sale_type"] == "mixed", head["sale_type"])
            check(f"  2 мөр, нийт {head['total']}₮",
                  len(head["items"]) == 2 and d(head["total"]) == mix_total, str(head["total"]))

        # Хосолсон төлбөр — нэг баримт хоёр хэрэгслээр
        half = (fuel_amt / 2).quantize(Decimal("0.01"))
        s, combo = post("/api/sales", {
            "sale_type": "fuel",
            "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"],
                       "nozzle_id": nozzle["id"], "qty": "10", "unit_price": str(price)}],
            "payments": [
                {"method": "cash", "amount": str(half), "received": str(half)},
                {"method": "card", "amount": str(fuel_amt - half), "ref_no": "COMBO"},
            ],
        })
        if expect("хосолсон төлбөр (бэлэн + карт)", s, combo):
            check("  2 төлбөрийн мөр",
                  len(combo.get("sale", combo).get("payments", [])) == 2,
                  str(combo.get("sale", combo).get("payments"))[:90])

    # ---- Салбарын төлбөрийн хэлбэр ------------------------------------------- #
    print("\n── САЛБАРЫН ТӨЛБӨРИЙН ХЭЛБЭР ──")
    login("owner")
    _, branch_rows = call("/api/branches")
    main_branch = branch_rows[0]
    s, methods = call(f"/api/branches/{main_branch['id']}/payment-methods")
    if expect(f"төлбөрийн хэлбэрүүд ({len(methods) if isinstance(methods, list) else 0})", s, methods):
        check("  анхдагчаар бүгд идэвхтэй", all(m["is_enabled"] for m in methods), str(methods)[:100])
        check("  бэлэн мөнгө түгжээтэй",
              next(m["locked"] for m in methods if m["method"] == "cash"), "")

    # QR-г хаана
    s, off = call(f"/api/branches/{main_branch['id']}/payment-methods",
                  [{"method": m["method"], "is_enabled": m["method"] != "qr"} for m in methods],
                  method="PUT")
    if expect("QR-г идэвхгүй болгов", s, off):
        check("  QR унтарсан", not next(m["is_enabled"] for m in off if m["method"] == "qr"), "")

    # Бэлэн мөнгийг хаах гэсэн оролдлого үл ойшоогдоно
    s, forced = call(f"/api/branches/{main_branch['id']}/payment-methods",
                     [{"method": m["method"], "is_enabled": False} for m in methods], method="PUT")
    if s == 200:
        check("бэлэн мөнгийг хаах боломжгүй",
              next(m["is_enabled"] for m in forced if m["method"] == "cash"), str(forced)[:80])

    # Кассчин унтраасан хэрэгслээр төлж чадахгүй
    call(f"/api/branches/{main_branch['id']}/payment-methods",
         [{"method": m["method"], "is_enabled": m["method"] != "qr"} for m in methods], method="PUT")
    login("cashier")
    s, r = post("/api/sales", {
        "sale_type": "fuel",
        "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"], "tank_id": nozzle["tank_id"],
                   "nozzle_id": nozzle["id"], "qty": "1", "unit_price": str(price)}],
        "payments": [{"method": "qr", "amount": str(price), "ref_no": "X"}],
    })
    check("унтраасан хэрэгслээр төлөхийг татгалзав",
          s == 422 and "идэвхгүй" in str(r), str(r)[:110])

    # Бүгдийг буцааж асаана — дараагийн шалгалтууд бүрэн ажиллана
    login("owner")
    call(f"/api/branches/{main_branch['id']}/payment-methods",
         [{"method": m["method"], "is_enabled": True} for m in methods], method="PUT")
    login("cashier")

    # ---- Гэрээт борлуулалт: мөнгөн дүнгээр оруулах -------------------------- #
    print("\n── МӨНГӨН ДҮНГЭЭР ГЭРЭЭТ БОРЛУУЛАЛТ ──")
    _, ct_list = call("/api/contracts")
    disc_contract = next((c for c in rows(ct_list) if d(c["price_discount_per_l"]) > 0), None)
    if disc_contract:
        disc = d(disc_contract["price_discount_per_l"])
        base_price = d(fuel_rec["price_per_liter"])
        net_price = base_price - disc
        wanted = Decimal("90000")
        # ПОС хөнгөлөлттэй үнээр литрийг бодно (3 орон), дүн нь хэвээр.
        liters_q = (wanted / net_price).quantize(Decimal("0.001"))
        s, disc_sale = post("/api/sales", {
            "sale_type": "fuel",
            "contract_id": disc_contract["id"],
            "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"],
                       "tank_id": nozzle["tank_id"], "nozzle_id": nozzle["id"],
                       "qty": str(liters_q), "unit_price": str(base_price),
                       "amount": str(wanted)}],
            "payments": [{"method": "contract", "amount": str(wanted),
                          "contract_id": disc_contract["id"]}],
        })
        if expect(f"{wanted}₮-өөр гэрээт борлуулалт", s, disc_sale):
            head = disc_sale.get("sale", disc_sale)
            check(f"  нийт дүн яг {wanted}₮", d(head["total"]) == wanted, head["total"])
            item = head["items"][0]
            check(f"  нэгж үнэ хөнгөлөгдсөн ({item['unit_price']}₮)",
                  d(item["unit_price"]) == net_price, item["unit_price"])

        # Хуурамч дүн бичихийг татгалзана
        s, r = post("/api/sales", {
            "sale_type": "fuel",
            "items": [{"item_type": "fuel", "fuel_id": nozzle["fuel_id"],
                       "tank_id": nozzle["tank_id"], "nozzle_id": nozzle["id"],
                       "qty": "10", "unit_price": str(base_price), "amount": "999999"}],
            "payments": [{"method": "cash", "amount": "999999", "received": "999999"}],
        })
        check("хэт зөрүүтэй дүн татгалзсан", s == 422, str(r)[:110])

    # ---- Задлан (грамлаж) зарах бүтээгдэхүүн -------------------------------- #
    print("\n── ГРАМ БҮТЭЭГДЭХҮҮН ──")
    s, bulk_page = call("/api/products?sale_mode=bulk&limit=50")
    bulk_items = rows(bulk_page)
    if expect(f"грам бүтээгдэхүүний жагсаалт ({len(bulk_items)})", s, bulk_page):
        check("  бүгд bulk горимтой",
              all(p["sale_mode"] == "bulk" for p in bulk_items), str(bulk_items)[:80])

    s, piece_page = call("/api/products?sale_mode=piece&limit=500")
    piece_skus = {p["sku"] for p in rows(piece_page)}
    check("ширхэг шүүлтэд грам бараа орохгүй",
          all(p["sku"] not in piece_skus for p in bulk_items), "")

    s, conv_page = call("/api/products?convertible=true&limit=50")
    conv_items = rows(conv_page)
    check(f"задлах боломжтой бараа ({len(conv_items)})",
          s == 200 and len(conv_items) > 0
          and all(p["is_convertible"] and p["bulk_product_name"] for p in conv_items),
          str(conv_items)[:90])

    if conv_items and bulk_items:
        source = next(p for p in conv_items if d(p["stock_qty"]) >= 2)
        target = next(b for b in bulk_items if b["id"] == source["bulk_product_id"])
        factor = d(source["bulk_factor"])
        src_before, tgt_before = d(source["stock_qty"]), d(target["stock_qty"])
        src_cost = d(source["avg_cost"])

        s, conv = post("/api/inventory/conversions", {"product_id": source["id"], "qty": "2"})
        if expect(f"задлав: {source['name_mn']} ×2 → {target['name_mn']}", s, conv):
            out_qty = d(conv["out_qty"])
            check(f"  гарсан хэмжээ {out_qty}", out_qty == 2 * factor, str(out_qty))
            check(f"  ширхэг үлдэгдэл {conv['source']['stock_qty']}",
                  d(conv["source"]["stock_qty"]) == src_before - 2, str(src_before))
            check(f"  грам үлдэгдэл {conv['target']['stock_qty']}",
                  d(conv["target"]["stock_qty"]) == tgt_before + out_qty, str(tgt_before))
            # Өртөг бүрэн шилжсэн: 1 ширхэгийн өртөг ÷ итгэлцүүр
            check(f"  нэгжийн өртөг {conv['target']['avg_cost']}",
                  abs(d(conv["target"]["avg_cost"]) - src_cost / factor) < Decimal("0.01"),
                  f"{src_cost} / {factor}")
            check(f"  шилжсэн өртөг {conv['cost']}₮",
                  d(conv["cost"]) == (2 * src_cost).quantize(Decimal("0.01")), str(conv["cost"]))

        s, txs = call(f"/api/inventory/transactions?product_id={target['id']}&limit=5")
        names = [t["tx_type_name"] for t in rows(txs)]
        check("нөөцийн дэвтэрт задлалт харагдана",
              any(t["tx_type"] == "convert_in" for t in rows(txs)), str(names))

        # Задлан бүтээгдэхүүнийг мөнгөн дүнгээр зарна (яг тэр дүнгээр)
        _, tgt_now = call(f"/api/products/{target['id']}")
        unit = d(tgt_now["price"])
        wanted = Decimal("30000")
        qty_q = (wanted / unit).quantize(Decimal("0.001"))
        stock_before = d(tgt_now["stock_qty"])
        s, bulk_sale = post("/api/sales", {
            "sale_type": "store",
            "items": [{"item_type": "product", "product_id": target["id"], "qty": str(qty_q),
                       "unit_price": str(unit), "amount": str(wanted)}],
            "payments": [{"method": "cash", "amount": str(wanted), "received": str(wanted)}],
        })
        if expect(f"грамлаж зарав ({qty_q}{tgt_now['unit']} = {wanted}₮)", s, bulk_sale):
            head = bulk_sale.get("sale", bulk_sale)
            check(f"  нийт дүн яг {wanted}₮", d(head["total"]) == wanted, head["total"])
            _, after = call(f"/api/products/{target['id']}")
            check("  грам үлдэгдэл хасагдсан",
                  d(after["stock_qty"]) == stock_before - qty_q,
                  f"{stock_before} → {after['stock_qty']}")

        s, r = post("/api/sales", {
            "sale_type": "store",
            "items": [{"item_type": "product", "product_id": target["id"], "qty": "1",
                       "unit_price": str(unit), "amount": "999999"}],
            "payments": [{"method": "cash", "amount": "999999", "received": "999999"}],
        })
        check("хуурамч дүнтэй грам мөр татгалзсан", s == 422, str(r)[:110])

        # Үлдэгдлээс их задлахыг татгалзана
        s, r = post("/api/inventory/conversions", {"product_id": source["id"], "qty": "100000"})
        check("үлдэгдлээс их задлахыг татгалзав", s == 422, str(r)[:110])

        # Грам бүтээгдэхүүнийг дахин задалж болохгүй
        s, r = post("/api/inventory/conversions", {"product_id": target["id"], "qty": "1"})
        check("грам бүтээгдэхүүн дахин задрахгүй", s == 422, str(r)[:110])

    # ---- Банкны хуулга ------------------------------------------------------ #
    print("\n── БАНКНЫ ХУУЛГА ──")
    login("owner")
    s, accounts = call("/api/bank-accounts")
    acc_items = accounts.get("items", []) if isinstance(accounts, dict) else []
    if expect(f"харилцах данс ({len(acc_items)})", s, accounts) and acc_items:
        main_acc = acc_items[0]
        check(
            f"  1110 = Σданс + хуваарилаагүй ({accounts['ledger_balance']}₮)",
            d(accounts["ledger_balance"])
            == sum((d(a["movement"]) for a in acc_items), Decimal("0")) + d(accounts["unassigned"]),
            f"{accounts['ledger_balance']} vs {accounts['unassigned']}",
        )

        _, cust_page = call("/api/customers?limit=50")
        smoke_contract = next(
            (c for cu in rows(cust_page) for c in cu["contracts"] if c["status"] == "active"), None
        )
        s, cfg = call(
            "/api/bank-statements/config",
            {
                "settlement_contract_id": smoke_contract["id"] if smoke_contract else None,
                "settlement_description": "ПОС орлого",
                "fee_account_code": "5371",
                "fee_description": "Банкны шимтгэл",
            },
            method="PUT",
        )
        check("тохиргоо хадгалав", s == 200 and cfg.get("fee_account_code") == "5371", str(cfg)[:90])

        xlsx = _demo_statement(main_acc["account_number"])
        s, st = upload_file("/api/bank-statements/upload", xlsx, f"Statement_MNT_{main_acc['account_number']}.xlsx")
        if expect(f"хуулга оруулав ({st.get('txn_count')} гүйлгээ)", s, st, codes=(201,)):
            check(f"  дансаар холбогдов ({st['bank_name']})", st["bank_account_id"] == main_acc["id"])
            check(f"  шимтгэл тусад нь ({st['fee']['count']} мөр, {st['fee']['total']}₮)",
                  st["fee"]["count"] == 2 and d(st["fee"]["total"]) == Decimal("5000"),
                  str(st["fee"]))
            check("  ПОС мөр урьдчилж бөглөгдөв",
                  any(t["is_settlement"] and t["contract_id"] for t in st["transactions"]),
                  "")

            sid = st["id"]
            post(f"/api/bank-statements/{sid}/fill-descriptions")
            _, st = call(f"/api/bank-statements/{sid}")
            for txn in st["transactions"]:
                if txn["is_fee"]:
                    continue
                body = (
                    {"contract_id": smoke_contract["id"]}
                    if txn["is_income"]
                    else {"expense_account_code": "5311"}
                )
                call(f"/api/bank-statements/{sid}/transactions/{txn['id']}", body, method="PATCH")

            _, st = call(f"/api/bank-statements/{sid}")
            check(f"  бүх мөр бэлэн ({st['ready_count']}/{st['txn_count']})",
                  st["ready_count"] == st["txn_count"], str(st["missing"]))

            before = d(main_acc["balance"])
            s, res = post(f"/api/bank-statements/{sid}/post-all")
            check(f"бүгдийг бүртгэв ({res.get('posted')})", s == 200 and res.get("posted") == 3,
                  str(res)[:120])
            s, st = post(f"/api/bank-statements/{sid}/post-fees")
            check(f"шимтгэлийг нэг зардлаар хаав (№{st['fee'].get('expense_number')})",
                  s == 200 and st["fee"]["posted"], str(st["fee"]))

            _, after_page = call("/api/bank-accounts")
            after_acc = next(a for a in after_page["items"] if a["id"] == main_acc["id"])
            # 2 000 000 орлого − 700 000 зарлага − 5 000 шимтгэл = +1 295 000
            check(f"дансны үлдэгдэл {d(after_acc['balance']) - before:+}₮",
                  d(after_acc["balance"]) - before == Decimal("1295000.00"),
                  f"{before} → {after_acc['balance']}")

            s, r = call(f"/api/bank-statements/{sid}", method="DELETE")
            check("бүртгэсэн хуулгыг устгахыг татгалзав", s == 422, str(r)[:90])

            post(f"/api/bank-statements/{sid}/unpost-fees")
            _, st = call(f"/api/bank-statements/{sid}")
            for txn in st["transactions"]:
                if txn["posted_at"] and not txn["is_fee"]:
                    post(f"/api/bank-statements/{sid}/transactions/{txn['id']}/unpost")
            _, back_page = call("/api/bank-accounts")
            back_acc = next(a for a in back_page["items"] if a["id"] == main_acc["id"])
            check(f"буцаахад үлдэгдэл сэргэв ({back_acc['balance']}₮)",
                  d(back_acc["balance"]) == before, f"{before} ≠ {back_acc['balance']}")
            s, _ = call(f"/api/bank-statements/{sid}", method="DELETE")
            check("хуулга устгав", s == 204, str(s))

    # ---- Худалдан авалт --------------------------------------------------- #
    print("\n── ХУДАЛДАН АВАЛТ ──")
    login("manager")
    _, sups = call("/api/suppliers")
    sup = rows(sups)[0]
    _, tanks = call("/api/tanks")
    tank = rows(tanks)[0]
    before_l = d(tank["current_l"])
    today = time.strftime("%Y-%m-%d")

    s, rec = post("/api/fuel-receipts", {
        "supplier_id": sup["id"], "tank_id": tank["id"], "fuel_id": tank["fuel_id"],
        "receipt_date": today, "invoice_no": f"SMOKE-{int(time.time())}",
        "liters": "5000.000", "unit_cost": "2500.000000", "freight_cost": "200000.00",
        "density": "0.7450", "temperature_c": "12.50",
    })
    if expect("шатахууны таталт үүсгэв (5000л)", s, rec):
        s, posted = post(f"/api/fuel-receipts/{rec['id']}/post")
        if expect("таталт бүртгэв", s, posted):
            _, t2 = call(f"/api/tanks/{tank['id']}")
            check("савны үлдэгдэл нэмэгдсэн", d(t2["current_l"]) == before_l + 5000,
                  f"{before_l} + 5000 ≠ {t2['current_l']}")

    _, prods = call("/api/products?limit=1")
    pr = rows(prods)[0]
    s, pu = post("/api/purchases", {
        "supplier_id": sup["id"], "purchase_date": today, "invoice_no": f"PU-{int(time.time())}",
        "items": [{"product_id": pr["id"], "qty": "10", "unit_cost": "12000.000000"}],
    })
    if expect("барааны худалдан авалт үүсгэв", s, pu):
        s, r = post(f"/api/purchases/{pu['id']}/post")
        expect("худалдан авалт бүртгэв", s, r)

    s, aps = call("/api/ap-invoices?status=open")
    if s == 200 and rows(aps):
        inv = rows(aps)[0]
        remaining = d(inv["amount_gross"]) - d(inv.get("amount_paid") or 0)
        pay_amt = min(remaining, Decimal("100000"))
        s, r = post("/api/ap-payments", {
            "ap_invoice_id": inv["id"], "amount": str(pay_amt),
            "paid_from": "bank", "payment_date": today,
        })
        expect(f"нийлүүлэгчид {pay_amt}₮ төлөв", s, r)
        s, r = post("/api/ap-payments", {
            "ap_invoice_id": inv["id"], "amount": "999999999.00",
            "paid_from": "bank", "payment_date": today,
        })
        check("илүү төлбөр татгалзсан", s == 422, str(r))

    # ---- Үйл ажиллагааны зардал ------------------------------------------ #
    print("\n── ЗАРДАЛ ──")
    login("manager")
    s, cats = call("/api/expense-categories")
    check(f"зардлын ангилал ({len(cats) if isinstance(cats, list) else 0})",
          s == 200 and isinstance(cats, list) and len(cats) >= 10, str(cats)[:100])

    sup_rows = rows(call("/api/suppliers")[1])
    sup_id = sup_rows[0]["id"] if sup_rows else None

    expense_cases = [
        ("5311", "450000", "cash", True, None, "цахилгаан (бэлнээр, НӨАТ-тай)"),
        ("5341", "2800000", "bank", False, None, "тээвэр (харилцахаас)"),
        ("5321", "1200000", "credit", True, sup_id, "түрээс (өглөгөөр)"),
    ]
    expense_total = Decimal("0")
    for code, amount, method, vat, sid, label in expense_cases:
        body = {"account_code": code, "amount": amount, "payment_method": method,
                "has_vat": vat, "description": label}
        if sid:
            body["supplier_id"] = sid
        s, r = post("/api/expenses", body)
        if expect(f"зардал: {label}", s, r):
            expense_total += Decimal(amount)
            if vat:
                check("  НӨАТ дүнгээс салгагдав", d(r["vat_amount"]) > 0, str(r["vat_amount"]))
            else:
                check("  НӨАТгүй зардал", d(r["vat_amount"]) == 0, str(r["vat_amount"]))

    # Өртгийн данс руу гараар зардал бичихийг хориглоно
    s, r = post("/api/expenses", {"account_code": "5101", "amount": "1000", "payment_method": "cash"})
    check("өртгийн данс руу зардал татгалзсан", s == 422, str(r))

    s, lst = call("/api/expenses")
    if expect("зардлын жагсаалт", s, lst):
        check(f"нийт зардал {lst['total_amount']}₮",
              d(lst["total_amount"]) >= expense_total, str(lst["total_amount"]))
        check("ангиллын задаргаа", len(lst.get("by_account") or []) >= 3,
              str(lst.get("by_account"))[:100])

    # ---- Цалин ------------------------------------------------------------ #
    print("\n── ЦАЛИН ──")
    login("manager")
    s, emps = call("/api/employees")
    emp_rows = rows(emps)
    check(f"ажилтны жагсаалт ({len(emp_rows)})", s == 200 and len(emp_rows) > 0, str(emps)[:100])

    if emp_rows:
        # Урьдчилгаа олгох → 1205 авлага үүснэ
        # Харилцахаас олгоно — ээлжийн кассыг сөрөг болгохгүйн тулд.
        # (Бэлэн мөнгөний интеграцийг цахилгааны зардал аль хэдийн шалгасан.)
        s, adv = post("/api/payroll/advances", {
            "employee_id": emp_rows[0]["id"], "amount": "300000",
            "paid_from": "bank", "note": "Туршилтын урьдчилгаа",
        })
        expect("урьдчилгаа олгов (300,000₮, харилцахаас)", s, adv)

    # Сарын дундуур ажилд орсон хүн — цалин хоногоор нь хуваарилагдана
    s, mid = post("/api/employees", {
        "full_name": "Дундуур Ажилтан", "position": "Кассчин",
        "base_salary": "3100000", "hire_date": "2026-07-15", "end_date": "2026-08-20",
    })
    if expect("сарын дундуур ажилласан ажилтан", s, mid):
        check("  ажилд орсон огноо хадгалагдсан", mid.get("hire_date") == "2026-07-15",
              str(mid.get("hire_date")))
        check("  ажлаас гарсан огноо хадгалагдсан", mid.get("end_date") == "2026-08-20",
              str(mid.get("end_date")))

        # 7-р сар: 31 хоногийн 17 (07-15 … 07-31)
        s, jul = post("/api/payroll/periods", {"year": 2026, "month": 7})
        if expect("  2026.07 тооцоо", s, jul):
            row = next((l for l in jul["lines"] if l["employee_name"] == "Дундуур Ажилтан"), None)
            if row:
                check(f"    сарын хоног 31", d(row["month_days"]) == 31, str(row["month_days"]))
                check(f"    ажилласан 17 хоног", d(row["worked_days"]) == 17, str(row["worked_days"]))
                check("    хэсэгчилсэн сар гэж тэмдэглэгдсэн", row["partial_month"] is True, "")
                check(f"    цалин 1,700,000₮", d(row["earned_salary"]) == d("1700000.00"),
                      str(row["earned_salary"]))
            else:
                check("    мөр үүссэн", False, "ажилтан жагсаалтад алга")

        # 2-р сар 28 хоног — уг ажилтан ороогүй байх ёстой
        s, feb = post("/api/payroll/periods", {"year": 2026, "month": 2})
        if expect("  2026.02 тооцоо (28 хоног)", s, feb):
            check("    сарын хоног 28",
                  bool(feb["lines"]) and d(feb["lines"][0]["month_days"]) == 28,
                  str(feb["lines"][0]["month_days"]) if feb["lines"] else "мөргүй")
            names = [l["employee_name"] for l in feb["lines"]]
            check("    ажилд ороогүй сард орсонгүй", "Дундуур Ажилтан" not in names, str(names))

        # 12-р сар — ажлаас гарсны дараа
        s, dec = post("/api/payroll/periods", {"year": 2026, "month": 12})
        if s in (200, 201):
            names = [l["employee_name"] for l in dec["lines"]]
            check("  ажлаас гарсны дараах сард орсонгүй",
                  "Дундуур Ажилтан" not in names, str(names))

            # Ноорог цуцлах — журналд бичигдээгүй тул ул мөргүй устана
            dec_id = dec["id"]
            s, _ = call(f"/api/payroll/periods/{dec_id}", method="DELETE")
            check("  ноорог цуцлав", s == 204, str(s))
            s, _ = call(f"/api/payroll/periods/{dec_id}")
            check("    цуцалсны дараа олдохгүй", s == 404, str(s))
            s, lst = call("/api/payroll/periods")
            check("    жагсаалтаас арилсан",
                  all(p["id"] != dec_id for p in rows(lst)), "")
            # Дахин үүсгэж болно
            s, again = post("/api/payroll/periods", {"year": 2026, "month": 12})
            check("    цуцалсан сарыг дахин үүсгэв", s in (200, 201), str(again)[:120])

    month = int(time.strftime("%m"))
    year = int(time.strftime("%Y"))
    s, period = post("/api/payroll/periods", {"year": year, "month": month})
    if expect(f"{year}.{month:02d} цалин тооцоолов", s, period):
        check(f"  {period['employee_count']} ажилтан", period["employee_count"] > 0, "")
        check(f"  нийт цалин {period['gross_total']}₮", d(period["gross_total"]) > 0, "")
        # Тооцооны дотоод тэнцэл: гарт олгох = нийт − НДШ − ХХОАТ − суутгал
        for ln in period["lines"]:
            expected = (d(ln["gross"]) - d(ln["si_employee"]) - d(ln["pit"])
                        - d(ln["advance"]) - d(ln["other_deduction"]))
            if d(ln["net"]) != expected:
                check(f"  {ln['employee_name']} тооцоо", False,
                      f"{ln['net']} ≠ {expected}")
                break
        else:
            check("  мөр бүрийн тооцоо зөв", True)

        # Урьдчилгааг суутгах
        if emp_rows:
            target = next((x for x in period["lines"] if x["employee_id"] == emp_rows[0]["id"]), None)
            if target:
                s, upd = call(f"/api/payroll/lines/{target['id']}", {"advance": "300000"}, method="PATCH")
                expect("  урьдчилгаа суутгав", s, upd)

        # Менежер батлах эрхгүй
        s, r = post(f"/api/payroll/periods/{period['id']}/approve", {})
        check("менежер батлах татгалзсан", s == 403, str(r)[:80])

        login("owner")
        s, approved = post(f"/api/payroll/periods/{period['id']}/approve", {})
        if expect("эзэн цалинг батлав", s, approved):
            check(f"  төлөв={approved['status']}", approved["status"] == "approved", "")
            check(f"  цалингийн өглөг {approved['owed_salary']}₮", d(approved["owed_salary"]) > 0, "")

        # Батлагдсаныг засах боломжгүй
        s, r = call(f"/api/payroll/lines/{period['lines'][0]['id']}", {"bonus": "1"}, method="PATCH")
        check("батлагдсаныг засах татгалзсан", s == 422, str(r)[:80])

        # Батлагдсаныг цуцлах боломжгүй — журналын бичилт үлдэх ёстой
        s, r = call(f"/api/payroll/periods/{period['id']}", method="DELETE")
        check("батлагдсаныг цуцлах татгалзсан", s == 422, str(r)[:80])

        # Гурван өглөгийг төлөх
        for tgt, label in (("salary", "цалин"), ("pit", "ХХОАТ"), ("social", "НДШ")):
            s, paid = post(f"/api/payroll/periods/{period['id']}/pay",
                           {"target": tgt, "paid_from": "bank"})
            expect(f"  {label} төлөв", s, paid)
        s, final = call(f"/api/payroll/periods/{period['id']}")
        check("бүх өглөг хаагдсан",
              d(final["owed_salary"]) == 0 and d(final["owed_pit"]) == 0 and d(final["owed_social"]) == 0,
              f"{final['owed_salary']}/{final['owed_pit']}/{final['owed_social']}")
        check(f"төлөв={final['status']}", final["status"] == "paid", final["status"])

    # ---- Нэхэмжлэх, авлага ------------------------------------------------ #
    print("\n── НЭХЭМЖЛЭХ, АВЛАГА ──")
    if rows(call("/api/contracts")[1]):
        ct = rows(call("/api/contracts")[1])[0]
        month = time.strftime("%Y-%m")
        s, r = post(f"/api/contracts/{ct['id']}/invoices/generate",
                    {"period_start": f"{month}-01", "period_end": f"{month}-28"})
        expect("сарын нэхэмжлэх үүсгэв", s, r)
        s, arl = call("/api/ar-invoices")
        if s == 200 and rows(arl):
            s, r = post("/api/ar-payments", {
                "contract_id": ct["id"], "ar_invoice_id": rows(arl)[0]["id"],
                "amount": "50000.00", "received_to": "bank", "payment_date": today,
            })
            expect("авлагын төлбөр бүртгэв", s, r)
        s, r = call(f"/api/contracts/{ct['id']}/statement?date_from={month}-01&date_to={month}-28")
        expect("гэрээний тооцоо", s, r)

    # ---- Зөвшөөрлийн урсгал ----------------------------------------------- #
    print("\n── ЗӨВШӨӨРӨЛ (эзний батламж) ──")
    _, fuels = call("/api/fuels")
    f0 = rows(fuels)[0]
    old_price = d(f0["price_per_liter"])
    s, r = call(f"/api/fuels/{f0['id']}", {"price_per_liter": "9999.00"}, method="PATCH")
    check("шууд үнэ засах хаагдсан", s == 422, str(r))
    s, pc = post("/api/price-changes", {
        "target_type": "fuel", "fuel_id": f0["id"],
        "new_price": str(old_price + 50), "reason": "Шалгалт",
    })
    if expect(f"үнийн өөрчлөлт хүсэв ({old_price} → {old_price + 50})", s, pc):
        _, mid = call("/api/fuels")
        check("батлагдтал үнэ хэвээр", d(rows(mid)[0]["price_per_liter"]) == old_price)
        login("owner")
        s, r = post(f"/api/price-changes/{pc['id']}/approve")
        if expect("эзэн үнийг баталлаа", s, r):
            _, aft = call("/api/fuels")
            check("шинэ үнэ хэрэгжсэн", d(rows(aft)[0]["price_per_liter"]) == old_price + 50,
                  str(rows(aft)[0]["price_per_liter"]))

    login("cashier")
    _, sales = call("/api/sales")
    target = next((x for x in rows(sales) if x["status"] == "completed"), None)
    if target:
        _, full = call(f"/api/sales/{target['id']}")
        s, rf = post("/api/refunds", {
            "sale_id": target["id"], "refund_type": "full",
            "items": [{"sale_item_id": ln["id"], "qty": ln["qty"]} for ln in full["items"]],
            "amount": full["total"], "reason": "Шалгалтын буцаалт", "restock": True,
        })
        if expect(f"буцаалт хүсэв (баримт №{target['number']})", s, rf):
            login("owner")
            s, r = post(f"/api/refunds/{rf['id']}/approve")
            if expect("эзэн буцаалтыг баталлаа", s, r):
                _, aft = call(f"/api/sales/{target['id']}")
                check("баримтын төлөв өөрчлөгдсөн", aft["status"] in ("refunded", "partial_refund"),
                      str(aft["status"]))

    # ---- Ээлж хаах -------------------------------------------------------- #
    print("\n── ЭЭЛЖ ХААХ (санаатай зөрүүтэй) ──")
    login("cashier")
    s, cur = call("/api/shifts/current")
    if cur:
        sh = cur.get("shift", cur)
        expected = d(cur["cash"]["expected_cash"])
        # Санаатай 5,000₮ дутагдал үүсгэнэ. Хэрэв кассаас их хэмжээний зардал,
        # урьдчилгаа гарсан бол хүлээгдэх дүн сөрөг байж болох тул 0-ээс доош
        # оруулахгүй (API сөрөг тоолсон бэлэн мөнгө хүлээж авахгүй).
        declared = expected - Decimal("5000")
        if declared < 0:
            declared = Decimal("0.00")
        _, tanks = call("/api/tanks")
        _, pumps = call("/api/pumps")
        nozzles = [n for p in rows(pumps) for n in p["nozzles"]]
        s, summary = post(f"/api/shifts/{sh['id']}/close", {
            "declared_cash": str(declared),
            "tank_dips": [{"tank_id": t["id"], "dip_liters": str(d(t["current_l"]) - Decimal("3"))}
                          for t in rows(tanks)],
            "totalizer_readings": [{"nozzle_id": n["id"], "reading": n["totalizer"]} for n in nozzles],
            "note": "Smoke test",
        })
        if expect("ээлж хаав", s, summary):
            shift_out = summary.get("shift", summary)
            check(f"кассын зөрүү бодогдсон ({shift_out.get('cash_over_short')}₮)",
                  d(shift_out.get("cash_over_short") or 0) == Decimal("-5000"),
                  str(shift_out.get("cash_over_short")))
            tank_rows = summary.get("tanks") or []
            check("савны хорогдол бүртгэгдсэн",
                  any(d(t.get("variance_l") or 0) != 0 for t in tank_rows),
                  json.dumps(tank_rows, ensure_ascii=False)[:200])
        s, x = download(f"/api/shifts/{sh['id']}/report.xlsx")
        check(f"ээлжийн тайлан Excel ({len(x):,} байт)", s == 200 and x[:2] == b"PK")

    # ---- Тайлан ----------------------------------------------------------- #
    print("\n── ТАЙЛАН, САМБАР ──")
    month = time.strftime("%Y-%m")
    rng = f"date_from={month}-01&date_to={month}-28"
    login("manager")
    for path, label in [
        ("/api/dashboards/cashier", "кассчны самбар"),
        (f"/api/reports/sales?granularity=day&{rng}", "борлуулалт (өдрөөр)"),
        (f"/api/reports/sales?granularity=month&{rng}", "борлуулалт (сараар)"),
        (f"/api/reports/fuel?{rng}", "түлшний тайлан"),
        (f"/api/reports/tender?{rng}", "төлбөрийн хэлбэр"),
        (f"/api/reports/tank-loss?{rng}", "савны хорогдол"),
        ("/api/inventory", "нөөцийн жагсаалт"),
        ("/api/ebarimt/queue", "и-баримтын дараалал"),
    ]:
        s, r = call(path)
        expect(label, s, r)

    for path, label in [
        (f"/api/reports/sales.xlsx?granularity=day&{rng}", "Excel: борлуулалт"),
        (f"/api/reports/fuel.xlsx?{rng}", "Excel: түлш"),
        ("/api/reports/inventory.xlsx", "Excel: нөөц"),
    ]:
        s, blob = download(path)
        check(f"{label} ({len(blob):,} байт)", s == 200 and blob[:2] == b"PK", str(blob[:120]))

    # ---- Бараа материалын тайлан /өртгөөр/ -------------------------------- #
    print("\n── БАРАА МАТЕРИАЛЫН ТАЙЛАН ──")
    login("manager")
    s, opts = call("/api/inventory-report/options")
    ok_opts = (s == 200 and isinstance(opts, dict)
               and len(opts.get("locations") or []) > 0
               and len(opts.get("fuels") or []) > 0)
    check("шүүлтийн сонголтууд", ok_opts, str(opts)[:100])

    year = time.strftime("%Y")
    full_range = f"date_from={year}-01-01&date_to={year}-12-31"

    s, rep = call(f"/api/inventory-report?{full_range}")
    if expect("бүтэн тайлан", s, rep):
        check(f"  {len(rep['rows'])} мөр", len(rep["rows"]) > 0, "")
        # Мөр бүрийн дотоод тэнцэл: эцсийн = эхний + орлого − зарлага
        bad = None
        for r in rep["rows"]:
            if d(r["closing_value"]) != d(r["opening_value"]) + d(r["in_value"]) - d(r["out_value"]):
                bad = r["name"]
                break
        check("  мөр бүрийн үлдэгдэл тэнцсэн", bad is None, f"зөрүүтэй: {bad}")

        # Ерөнхий дэвтэртэй тулгах — 1301 + 1302
        login("owner")
        s2, tb = call("/api/accounting/trial-balance")
        ledger = sum(d(a["balance"]) for a in (tb.get("accounts") or [])
                     if a["code"] in ("1301", "1302"))
        check(f"  ерөнхий дэвтэртэй тэнцсэн ({ledger}₮)",
              d(rep["totals"]["closing_value"]) == ledger,
              f"тайлан {rep['totals']['closing_value']} ≠ дэвтэр {ledger}")
        login("manager")

    # Шүүлт: тодорхой сав + түлш + задаргаа
    locs = (opts or {}).get("locations") or []
    fuels = (opts or {}).get("fuels") or []
    if locs and fuels:
        s, filtered = call(
            f"/api/inventory-report?{full_range}"
            f"&tank_id={locs[0]['id']}&fuel_id={fuels[0]['id']}&include_details=true"
        )
        if expect("шүүсэн тайлан (сав + түлш + задаргаа)", s, filtered):
            check("  шүүлтийн нөхцөл бичигдсэн", bool(filtered.get("filter_text")),
                  str(filtered.get("filter_text"))[:80])
            leaf = [r for r in filtered["rows"] if r["details"]]
            check("  задаргааны мөр гарсан", len(leaf) > 0, "")

    # Гүйлгээний төрлөөр шүүх
    s, only_in = call(f"/api/inventory-report?{full_range}&tx_type=in")
    if expect("зөвхөн орлого", s, only_in):
        check("  зарлага 0", d(only_in["totals"]["out_value"]) == 0,
              str(only_in["totals"]["out_value"]))

    # Бүлэглэл солих
    s, grouped = call(f"/api/inventory-report?{full_range}&group_by=item")
    expect("бүлэглэл: зөвхөн бараа", s, grouped)

    # Excel
    s, blob = download(f"/api/inventory-report.xlsx?{full_range}&include_details=true")
    check(f"Excel: бараа материал ({len(blob):,} байт)",
          s == 200 and blob[:2] == b"PK", str(blob[:120]))

    # ---- Салбар ------------------------------------------------------------ #
    print("\n── САЛБАР ──")
    login("owner")
    s, branches = call("/api/branches")
    ok = s == 200 and isinstance(branches, list) and len(branches) >= 1
    check(f"салбарын жагсаалт ({len(branches) if ok else 0})", ok, str(branches)[:100])

    # Дахин ажиллуулахад тэсвэртэй: байвал түүнийг ашиглана.
    existing = next((b for b in (branches or []) if b["code"] == "T9"), None)
    if existing:
        new_branch = existing
        check("эзэн салбар үүсгэв (аль хэдийн бий)", True)
    else:
        s, created = post("/api/branches", {
            "code": "T9", "name": "Туршилтын салбар", "address": "Тест", "sort_order": 9,
        })
        new_branch = created if expect("эзэн салбар үүсгэв", s, created) else None

    # Менежер салбар үүсгэж чадахгүй
    login("manager")
    s, r = post("/api/branches", {"code": "T8", "name": "Зөвшөөрөлгүй"})
    check("менежер салбар үүсгэх татгалзсан", s == 403, str(r)[:80])

    # Кассчинд салбар заавал
    login("owner")
    s, roles = call("/api/roles")
    cashier_role = next((r for r in rows(roles) if r["code"] == "cashier"), None)
    if cashier_role and new_branch:
        s, r = post("/api/users", {
            "username": "smoke_cashier", "full_name": "Смок Кассчин",
            "pin": "000000", "role_id": cashier_role["id"],
        })
        check("салбаргүй кассчин татгалзсан", s == 422, str(r)[:80])

        s, user = post("/api/users", {
            "username": "smoke_cashier", "full_name": "Смок Кассчин",
            "pin": "000000", "role_id": cashier_role["id"],
            "branch_id": new_branch["id"],
        })
        if s == 422:  # аль хэдийн бүртгэгдсэн — байгаагаа авна
            s, existing_users = call("/api/users?q=smoke_cashier")
            found = next((u for u in rows(existing_users) if u["username"] == "smoke_cashier"), None)
            if found:
                s, user = 201, found
        if expect("салбартай кассчин үүсгэв", s, user):
            check(f"  салбар: {user.get('branch_name')}",
                  user.get("branch_id") == new_branch["id"], str(user)[:80])

            # Нэвтрэхэд салбар автоматаар сонгогдоно
            s, tiles = call("/api/auth/users")
            tile = next((u for u in tiles if u["username"] == "smoke_cashier"), None)
            if tile:
                s, body = post("/api/auth/login", {"user_id": tile["id"], "pin": "000000"})
                if expect("  шинэ кассчин нэвтэрлээ", s, body):
                    u = body["user"]
                    check(f"  салбар автоматаар: {u.get('branch', {}).get('name') if u.get('branch') else '—'}",
                          bool(u.get("branch")) and u["branch"]["id"] == new_branch["id"],
                          str(u.get("branch")))
                    check("  all_branches=False", u.get("all_branches") is False, str(u.get("all_branches")))

    # Менежер, эзэн бүх салбарыг хардаг
    for role in ("manager", "owner"):
        body = login(role)
        u = body["user"]
        check(f"{role} бүх салбарыг харна",
              u.get("all_branches") is True and u.get("branch") is None,
              f"all={u.get('all_branches')} branch={u.get('branch')}")

    # Ажилтантай салбарыг идэвхгүй болгохыг хориглоно
    login("owner")
    if new_branch:
        s, r = call(f"/api/branches/{new_branch['id']}", {"is_active": False}, method="PATCH")
        check("ажилтантай салбарыг хаахыг хориглов", s == 422, str(r)[:90])

    # ---- Салбарын нөөц ------------------------------------------------------ #
    print("\n── САЛБАРЫН НӨӨЦ ──")
    login("owner")
    s, prods = call("/api/products?limit=5")
    product = next((x for x in rows(prods) if x["is_active"]), None)
    s, sups = call("/api/suppliers?limit=3")
    supplier = (rows(sups) or [None])[0]
    if new_branch and product and supplier:
        # Туршилтын салбарын нөөцөд худалдан авалт хийнэ
        s, pu = post("/api/purchases", {
            "supplier_id": supplier["id"],
            "branch_id": new_branch["id"],
            "purchase_date": time.strftime("%Y-%m-%d"),
            "items": [{"product_id": product["id"], "qty": "7", "unit_cost": "1000"}],
        })
        if expect("салбар руу худалдан авалт үүсгэв", s, pu):
            s, posted = post(f"/api/purchases/{pu['id']}/post")
            expect("  худалдан авалт баталгаажив", s, posted)

            s, inv = call(f"/api/inventory?search={product['sku']}")
            row = next((x for x in rows(inv) if x["product_id"] == product["id"]), None)
            if row:
                per_branch = {b["branch_name"]: d(b["qty"]) for b in row.get("branches", [])}
                check(f"  салбарын задаргаа: {per_branch}",
                      d(row.get("branches", [{}])[0].get("qty", 0)) >= 0
                      and sum(per_branch.values()) == d(row["stock_qty"]),
                      f"Σ={sum(per_branch.values())} нийт={row['stock_qty']}")
                tb_qty = per_branch.get(new_branch["name"], d(0))
                check("  туршилтын салбарт 7ш орсон", tb_qty >= 7, str(per_branch))

            # Салбараар шүүсэн нөөц
            s, inv_b = call(f"/api/inventory?branch_id={new_branch['id']}&search={product['sku']}")
            row_b = next((x for x in rows(inv_b) if x["product_id"] == product["id"]), None)
            check("  салбараар шүүсэн үлдэгдэл",
                  row_b is not None and d(row_b["stock_qty"]) >= 7,
                  str(row_b and row_b["stock_qty"]))

    # ---- Салбарын үнэ -------------------------------------------------------- #
    print("\n── САЛБАРЫН ҮНЭ ──")
    login("manager")
    s, fuels_list = call("/api/fuels")
    fuel = next((f for f in rows(fuels_list) if f["is_active"]), None)
    if new_branch and fuel:
        base_price = d(fuel["price_per_liter"])
        branch_new = str(base_price + 55)
        s, pc = post("/api/price-changes", {
            "target_type": "fuel", "fuel_id": fuel["id"],
            "branch_id": new_branch["id"], "new_price": branch_new,
            "reason": "Салбарын туршилт",
        })
        if s == 422:  # өмнөх ажиллагаанаас хүлээгдэж буй хүсэлт байж болно
            s, lst = call("/api/price-changes?status=pending")
            pc = next((x for x in rows(lst)
                       if x["fuel_id"] == fuel["id"] and x.get("branch_id") == new_branch["id"]), None)
            s = 201 if pc else 422
        if expect("салбарын үнийн хүсэлт", s, pc):
            check("  салбарын нэр бичигдсэн", pc.get("branch_name") == new_branch["name"],
                  str(pc.get("branch_name")))
            login("owner")
            s, approved = post(f"/api/price-changes/{pc['id']}/approve")
            if expect("  эзэн батлав", s, approved):
                # Суурь үнэ хөдлөөгүй
                s, f2 = call(f"/api/fuels/{fuel['id']}")
                check("  суурь үнэ хөдлөөгүй", d(f2["price_per_liter"]) == base_price,
                      f"{f2['price_per_liter']} vs {base_price}")

        # Барааны салбарын үнэ — ПОС-ын салбарын жагсаалтад тусна
        if product:
            prod_new = str(d(product["price"]) + 250)
            s, pc2 = post("/api/price-changes", {
                "target_type": "product", "product_id": product["id"],
                "branch_id": new_branch["id"], "new_price": prod_new,
                "reason": "Салбарын туршилт",
            })
            if s == 201:
                s, _ = post(f"/api/price-changes/{pc2['id']}/approve")
                s, plist = call(f"/api/products?branch_id={new_branch['id']}&search={product['sku']}")
                prow = next((x for x in rows(plist) if x["id"] == product["id"]), None)
                check("  салбарын барааны үнэ үйлчилж байна",
                      prow is not None and d(prow["price"]) == d(prod_new),
                      f"{prow and prow['price']} vs {prod_new}")
                s, plist0 = call(f"/api/products?search={product['sku']}")
                prow0 = next((x for x in rows(plist0) if x["id"] == product["id"]), None)
                check("  суурь барааны үнэ хөдлөөгүй",
                      prow0 is not None and d(prow0["price"]) == d(product["price"]),
                      f"{prow0 and prow0['price']} vs {product['price']}")

    # ---- Харилцагчийн карт -------------------------------------------------- #
    print("\n── ХАРИЛЦАГЧИЙН КАРТ ──")
    login("owner")
    s, cust = post("/api/customers", {
        "last_name": "Батын", "name": "Смок Хэрэглэгч", "type": "individual",
        "phone": "99110011", "phone2": "88220022", "email": "smoke@test.mn",
        "province": "Хөвсгөл", "district": "Цагаан-Уул",
        "credit_limit": "1500000",
    })
    if s == 422:  # өмнөх ажиллагаанаас үлдсэн — регистргүй тул нэрээр олно
        s, lst = call("/api/customers?search=" + urllib.parse.quote("Смок Хэрэглэгч"))
        cust = next((x for x in rows(lst) if x["name"] == "Смок Хэрэглэгч"), None)
        s = 201 if cust else 422
    if expect("дэлгэрэнгүй карттай харилцагч", s, cust):
        check(f"  байршил: {cust['province']} - {cust['district']}",
              cust["province"] == "Хөвсгөл" and cust["district"] == "Цагаан-Уул", str(cust)[:80])
        check("  овог нэр нийлсэн", cust["full_name"] == "Батын Смок Хэрэглэгч", cust["full_name"])
        check("  зээлийн лимит", d(cust["credit_limit"]) == d("1500000"), cust["credit_limit"])
        cid = cust["id"]

        # PDF хавсаргах (multipart, агуулгаар шалгадаг)
        boundary = "----kolonksmoke"
        pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"
        mp_body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"geree.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode() + pdf + f"\r\n--{boundary}--\r\n".encode()

        def _upload(content_body):
            req = urllib.request.Request(
                BASE + f"/api/customers/{cid}/contract-file", data=content_body, method="POST")
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("Authorization", f"Bearer {_token}")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")[:200]

        s, up = _upload(mp_body)
        if expect("  гэрээний PDF хавсаргав", s, up):
            check("    has_contract_file", up["has_contract_file"] is True, str(up)[:80])
        s, blob = download(f"/api/customers/{cid}/contract-file")
        check("  PDF татагдана", s == 200 and blob[:5] == b"%PDF-", str(blob[:20]))

        bad_body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"x.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode() + b"MZ not a pdf" + f"\r\n--{boundary}--\r\n".encode()
        s, r = _upload(bad_body)
        check("  PDF биш файл татгалзсан", s == 422, str(r)[:80])

        # Шүүлтүүд: байршил, бүх мэдээлэл, үүсгэсэн огноо
        s, r = call("/api/customers?province=" + urllib.parse.quote("Хөвсгөл")
                    + "&district=" + urllib.parse.quote("Цагаан-Уул"))
        check("  байршлаар шүүх", s == 200 and any(x["id"] == cid for x in rows(r)), str(r)[:80])
        s, r = call("/api/customers?search=88220022")
        check("  утас 2-оор хайх", s == 200 and any(x["id"] == cid for x in rows(r)), str(r)[:80])
        today = time.strftime("%Y-%m-%d")
        s, r = call(f"/api/customers?created_from={today}&created_to={today}")
        check("  үүсгэсэн огноогоор шүүх", s == 200 and any(x["id"] == cid for x in rows(r)), "")
        s, r = call("/api/customers?created_from=2020-01-01&created_to=2020-01-02")
        check("  огнооны гадуурх шүүлт хоосон", s == 200 and len(rows(r)) == 0, str(len(rows(r))))

    # ---- Тоолуурын заалт идэвхтэй/идэвхгүй ---------------------------------- #
    print("\n── ТООЛУУРЫН ЗААЛТЫН ТОХИРГОО ──")
    login("owner")
    s, cfg = call("/api/settings")
    check("анхдагч нь идэвхтэй", cfg.get("shift_totalizer_enabled") is True,
          str(cfg.get("shift_totalizer_enabled")))

    _, tk = call("/api/tanks")
    _, pm = call("/api/pumps")
    all_nozzles = [n for p in rows(pm) for n in p["nozzles"]]
    open_dips = [{"tank_id": t["id"], "dip_liters": t["current_l"]} for t in rows(tk)]
    open_reads = [{"nozzle_id": n["id"], "reading": n["totalizer"]} for n in all_nozzles]

    # Ээлжийг КАССЧИН нээнэ — олон салбартай үед салбартай хэрэглэгч л нээж чадна.
    login("cashier")

    # Идэвхтэй үед заалт заавал
    s, r = post("/api/shifts/open",
                {"opening_cash": "0", "tank_dips": open_dips, "totalizer_readings": []})
    check("  идэвхтэй үед заалтгүй нээхийг татгалзав", s == 422, str(r)[:90])
    s, r = post("/api/shifts/open",
                {"opening_cash": "0", "tank_dips": open_dips, "totalizer_readings": open_reads[:1]})
    check("  дутуу заалтыг татгалзав", s == 422, str(r)[:90])

    s, opened = post("/api/shifts/open",
                     {"opening_cash": "100000", "tank_dips": open_dips,
                      "totalizer_readings": open_reads})
    if expect("  бүрэн заалтаар нээгдэв", s, opened):
        tmp_id = opened["shift"]["id"]
        s, r = post(f"/api/shifts/{tmp_id}/close",
                    {"declared_cash": "100000", "tank_dips": open_dips, "totalizer_readings": []})
        check("  хаахад ч заалт заавал", s == 422, str(r)[:90])
        s, rep = post(f"/api/shifts/{tmp_id}/close",
                      {"declared_cash": "100000", "tank_dips": open_dips,
                       "totalizer_readings": open_reads})
        if expect("  бүрэн заалтаар хаагдав", s, rep):
            check("    тайланд заалт бүртгэгдсэн",
                  any(d(n["opening_reading"]) > 0 or d(n["closing_reading"]) > 0
                      for n in rep.get("nozzles", [])), "")

    # Унтраасан үед зөвхөн касс + сав (тохиргоог зөвхөн эзэн солино)
    login("owner")
    s, _ = call("/api/settings/shift_totalizer_enabled", {"value": False}, method="PUT")
    check("  эзэн тоолуурыг унтраав", s == 200, str(s))
    login("cashier")
    s, opened2 = post("/api/shifts/open",
                      {"opening_cash": "100000", "tank_dips": open_dips, "totalizer_readings": []})
    if expect("  зөвхөн касс+савaap нээгдэв", s, opened2):
        tmp2 = opened2["shift"]["id"]
        s, rep2 = post(f"/api/shifts/{tmp2}/close",
                       {"declared_cash": "100000", "tank_dips": open_dips,
                        "totalizer_readings": []})
        if expect("  заалтгүй хаагдав", s, rep2):
            check("    заалт огт бүртгэгдээгүй",
                  all(d(n["opening_reading"]) == 0 and d(n["closing_reading"]) == 0
                      for n in rep2.get("nozzles", [])), "")

    # Кассчин тохиргоо өөрчилж чадахгүй
    s, r = call("/api/settings/shift_totalizer_enabled", {"value": True}, method="PUT")
    check("  кассчин тохиргоо солихыг татгалзав", s == 403, str(r)[:90])

    # Анхдагч төлөвт буцаана — дараагийн шалгалтууд заалттай ажиллана
    login("owner")
    call("/api/settings/shift_totalizer_enabled", {"value": True}, method="PUT")

    # ---- Салбарын хамрах хүрээ, эрх ------------------------------------------ #
    print("\n── САЛБАРЫН ХАМРАХ ХҮРЭЭ ──")
    login("owner")
    if new_branch:
        # Туршилтын салбарт сав + насос үүсгэж кассчны харагдацыг шалгана
        fuel_rows = rows(call("/api/fuels")[1])
        s, t9tank = post("/api/tanks", {
            "branch_id": new_branch["id"], "name": "T9-сав", "fuel_id": fuel_rows[0]["id"],
            "capacity_l": "10000", "min_level_l": "500",
        })
        if s == 422:  # өмнөх ажиллагаанаас үлдсэн
            s, lst = call(f"/api/tanks?branch_id={new_branch['id']}")
            t9tank = next((x for x in rows(lst) if x["name"] == "T9-сав"), None)
            s = 201 if t9tank else 422
        if expect("өөр салбарт сав үүсгэв", s, t9tank):
            check(f"  салбарын нэр: {t9tank.get('branch_name')}",
                  t9tank.get("branch_name") == new_branch["name"], str(t9tank)[:90])

            s, t9pump = post("/api/pumps", {
                "number": 91, "name": "T9-насос", "branch_id": new_branch["id"],
                "position_x": 0, "position_y": 0,
                "nozzles": [{"nozzle_number": 1, "fuel_id": fuel_rows[0]["id"],
                             "tank_id": t9tank["id"], "totalizer": "0"}],
            })
            if s == 422:
                s, lst = call(f"/api/pumps?branch_id={new_branch['id']}")
                t9pump = next((x for x in rows(lst) if x["name"] == "T9-насос"), None)
                s = 201 if t9pump else 422
            expect("  өөр салбарт насос үүсгэв", s, t9pump)

        # Кассчин зөвхөн өөрийн салбарынхыг харна
        login("cashier")
        s, cp = call("/api/pumps")
        branches_seen = {p.get("branch_name") for p in rows(cp)}
        check(f"кассчин зөвхөн өөрийн салбарын насос ({branches_seen})",
              branches_seen == {"Төв салбар"}, str(branches_seen))
        s, ct = call("/api/tanks")
        tank_branches = {x.get("branch_name") for x in rows(ct)}
        check(f"кассчин зөвхөн өөрийн салбарын сав ({tank_branches})",
              tank_branches == {"Төв салбар"}, str(tank_branches))
        s, forced = call(f"/api/pumps?branch_id={new_branch['id']}")
        check("кассчин өөр салбар шаардсан ч өөрийнхөө л насосыг харна",
              {p.get("branch_name") for p in rows(forced)} == {"Төв салбар"}, "")

        # Эзэн бүгдийг харна
        login("owner")
        s, op = call("/api/pumps")
        check("эзэн бүх салбарын насосыг харна",
              len({p.get("branch_name") for p in rows(op)}) >= 2,
              str({p.get("branch_name") for p in rows(op)}))

        # Нэг кассчин 2 салбарт бүртгэгдэхгүй
        role_rows = rows(call("/api/roles")[1])
        c_role = next(r for r in role_rows if r["code"] == "cashier")
        s, r = post("/api/users", {
            "username": "dorj", "full_name": "Хуулбар Дорж", "pin": "000000",
            "role_id": c_role["id"], "branch_id": new_branch["id"],
        })
        check("давхар нэвтрэх нэр татгалзсан", s == 422 and "аль хэдийн бүртгэлтэй" in str(r),
              str(r)[:120])

        user_rows = rows(call("/api/users?limit=200")[1])
        dorj = next((u for u in user_rows if u["username"] == "dorj"), None)
        if dorj:
            s, r = call(f"/api/users/{dorj['id']}", {"branch_id": new_branch["id"]}, method="PATCH")
            check("өөр салбар руу шилжүүлэхийг сануулав",
                  s == 422 and "бүртгэлтэй байна" in str(r), str(r)[:130])

        # Салбараар хэрэглэгч шүүх
        s, filtered = call(f"/api/users?branch_id={new_branch['id']}")
        check("хэрэглэгчийг салбараар шүүх",
              s == 200 and all(u["branch_id"] == new_branch["id"] for u in rows(filtered)),
              str(len(rows(filtered))))

    # ---- Цалингийн тохиргоо, НДШ -------------------------------------------- #
    print("\n── ЦАЛИНГИЙН ТОХИРГОО ──")
    login("owner")
    s, emps = call("/api/employees")
    emp_rows = rows(emps)
    check("ажилтанд НДШ тэмдэг бий", all("si_enabled" in e for e in emp_rows), str(emp_rows[:1])[:120])

    if emp_rows:
        target = emp_rows[0]
        s, off = call(f"/api/employees/{target['id']}", {"si_enabled": False}, method="PATCH")
        if expect("НДШ бодохгүй болгов", s, off):
            check("  тэмдэг унтарсан", off["si_enabled"] is False, str(off)[:80])

        # Тухайн ажилтантай шинэ сар үүсгээд НДШ 0 болохыг шалгана
        s, per = post("/api/payroll/periods",
                      {"year": 2024, "month": 5, "employee_ids": [target["id"]]})
        if expect("сонгосон ажилтнаар сар үүсгэв", s, per):
            check(f"  зөвхөн 1 ажилтан ({per['employee_count']})",
                  per["employee_count"] == 1, str(per["employee_count"]))
            line = per["lines"][0]
            check("  НДШ (ажилтан) 0", d(line["si_employee"]) == 0, line["si_employee"])
            check("  НДШ (ажил олгогч) 0", d(line["si_employer"]) == 0, line["si_employer"])
            check("  ХХОАТ мөн 0", d(line["pit"]) == 0, line["pit"])
            check("  гарт олгох = нийт цалин",
                  d(line["net"]) == d(line["gross"]) - d(line["advance"]) - d(line["other_deduction"]),
                  f"{line['net']} vs {line['gross']}")

            # Дахин тооцоолоход бусад ажилтан нэмэгдэхгүй
            s, again = post(f"/api/payroll/periods/{per['id']}/recalculate")
            check("  дахин тооцоолоход сонголт хэвээр",
                  s == 200 and again["employee_count"] == 1, str(again.get("employee_count")))
            call(f"/api/payroll/periods/{per['id']}", method="DELETE")

        call(f"/api/employees/{target['id']}", {"si_enabled": True}, method="PATCH")

    # Мөр бүрд НДШ бодох эсэхийг цонхноос солино
    s, per2 = post("/api/payroll/periods", {"year": 2024, "month": 7})
    if expect("НДШ туршилтын сар", s, per2) and per2["lines"]:
        one = per2["lines"][0]
        check("  мөрд НДШ тэмдэг бий", "si_enabled" in one, str(one)[:100])
        s, off2 = call(f"/api/payroll/lines/{one['id']}", {"si_enabled": False}, method="PATCH")
        if expect("  мөрийн НДШ унтраав", s, off2):
            changed = next(x for x in off2["lines"] if x["id"] == one["id"])
            check("    НДШ 0 болов",
                  d(changed["si_employee"]) == 0 and d(changed["si_employer"]) == 0,
                  f"{changed['si_employee']}/{changed['si_employer']}")
            check("    ХХОАТ мөн 0", d(changed["pit"]) == 0, changed["pit"])
            check("    гарт олгох нэмэгдсэн", d(changed["net"]) > d(one["net"]),
                  f"{one['net']} → {changed['net']}")
        s, on2 = call(f"/api/payroll/lines/{one['id']}", {"si_enabled": True}, method="PATCH")
        if s == 200:
            back = next(x for x in on2["lines"] if x["id"] == one["id"])
            check("  буцааж асаахад сэргэсэн", d(back["net"]) == d(one["net"]),
                  f"{back['net']} vs {one['net']}")
        call(f"/api/payroll/periods/{per2['id']}", method="DELETE")

    # Хувь хэмжээг тохируулах
    s, r = call("/api/settings/payroll_pit_credit", {"value": "25000"}, method="PUT")
    check("ХХОАТ-ын хөнгөлөлт солив", s == 200, str(r)[:80])
    s, cfg2 = call("/api/settings")
    check("  тохиргоо хадгалагдсан", str(cfg2.get("payroll_pit_credit")) == "25000",
          str(cfg2.get("payroll_pit_credit")))
    call("/api/settings/payroll_pit_credit", {"value": "20000"}, method="PUT")

    # ---- Салбарын самбар, тохиргоо ------------------------------------------ #
    print("\n── САЛБАРЫН САМБАР, ТОХИРГОО ──")
    login("owner")
    s, dash = call("/api/dashboards/owner")
    if expect("эзний самбар", s, dash):
        check(f"  салбарын задаргаа ({len(dash.get('branches', []))})",
              len(dash.get("branches", [])) >= 2, str(dash.get("branches"))[:120])
        check("  топ насосны ойлголт устсан", "top_pumps" not in dash, str(list(dash.keys()))[:150])

    if new_branch:
        s, one = call(f"/api/dashboards/owner?branch_id={new_branch['id']}")
        if expect("нэг салбарын самбар", s, one):
            check("  задаргаа хоосон (нэг салбарын горим)", one.get("branches") == [], str(one.get("branches")))

    s, r = call("/api/reports/top-pumps")
    check("top-pumps endpoint устсан", s == 404, str(s))

    # Насосны байршил ба салбарын шүүлт
    s, pm = call("/api/pumps")
    all_pumps = rows(pm)
    check("насос салбартай, байршилтай",
          all(p.get("branch_id") and "position_x" in p for p in all_pumps),
          str(all_pumps[:1])[:150])
    if all_pumps:
        first = all_pumps[0]
        s, moved = call(f"/api/pumps/{first['id']}",
                        {"position_x": 3, "position_y": 2}, method="PATCH")
        if expect("насосны байршил солив", s, moved):
            check("  байршил хадгалагдсан",
                  moved["position_x"] == 3 and moved["position_y"] == 2, str(moved)[:90])
            call(f"/api/pumps/{first['id']}",
                 {"position_x": first["position_x"], "position_y": first["position_y"]},
                 method="PATCH")

    if new_branch:
        s, bp = call(f"/api/pumps?branch_id={new_branch['id']}")
        check("салбараар насос шүүх",
              s == 200 and all(p["branch_id"] == new_branch["id"] for p in rows(bp)),
              str(len(rows(bp))))

    # ---- Дата backup --------------------------------------------------------- #
    print("\n── ДАТА BACKUP ──")
    login("owner")
    s, bdir = call("/api/backups/directory")
    if expect("хадгалах хавтас", s, bdir):
        check(f"  анхдагч: {bdir['directory']}", bdir["is_default"] is True and bdir["writable"],
              str(bdir))

    s, made = post("/api/backups")
    if expect("нөөцлөлт үүсгэв", s, made):
        check(f"  файл {made['filename']} ({made['size_mb']} МБ)", d(made["size_bytes"]) > 0, str(made))
        st, blob = download(f"/api/backups/{made['filename']}/download")
        check("  татагдав (pg_dump хэлбэр)", st == 200 and blob[:5] == b"PGDMP", str(blob[:20]))

    # Хавтас солих — шинэ хавтас хоосон эхэлж, тэнд нөөцлөгдөнө
    import tempfile as _tempfile

    test_dir = os.path.join(_tempfile.gettempdir(), "kolonk_smoke_backup")
    s, moved = call("/api/backups/directory", {"directory": test_dir}, method="PUT")
    if expect("хавтас солив", s, moved):
        check("  анхдагч биш болов", moved["is_default"] is False, str(moved))
        s, lst = call("/api/backups")
        before = len(rows(lst))
        s, made2 = post("/api/backups")
        if expect("  шинэ хавтсанд нөөцлөв", s, made2):
            check("    файл бодитоор үүссэн",
                  os.path.isfile(os.path.join(test_dir, made2["filename"])), test_dir)
            s, lst2 = call("/api/backups")
            check("    жагсаалт зөвхөн шинэ хавтсаас", len(rows(lst2)) == before + 1,
                  f"{before} → {len(rows(lst2))}")

    s, r = call("/api/backups/directory", {"directory": "Z:\\baihgui\\zam"}, method="PUT")
    check("байхгүй хавтсыг татгалзав", s == 422, str(r)[:90])

    s, back = call("/api/backups/directory", {"directory": ""}, method="PUT")
    check("анхдагчид буцаав", s == 200 and back["is_default"] is True, str(back))

    login("cashier")
    s, r = post("/api/backups")
    check("кассчин нөөцлөх татгалзсан", s == 403, str(r)[:90])
    login("owner")

    # ---- Ажилчдын шүүлт ------------------------------------------------------ #
    print("\n── АЖИЛЧДЫН ШҮҮЛТ ──")
    login("owner")
    s, r = call("/api/employees")
    all_emp = len(rows(r))
    ok = s == 200 and all_emp >= 1 and rows(r)[0].get("branch_name") is not None
    check(f"ажилтны жагсаалт ({all_emp}, салбарын нэртэй)", ok, str(rows(r)[:1])[:120])

    s, r = call("/api/employees?search=" + urllib.parse.quote("Нягтлан"))
    check("  албан тушаалаар хайх", s == 200 and
          all("Нягтлан" in (x.get("position") or "") for x in rows(r)) and len(rows(r)) >= 1,
          str([x["full_name"] for x in rows(r)]))

    s, r = call("/api/employees?is_active=true")
    check("  ажиллаж буйгаар шүүх", s == 200 and all(x["is_active"] for x in rows(r)), "")

    if new_branch:
        s, r = call(f"/api/employees?branch_id={new_branch['id']}")
        check("  салбараар шүүх", s == 200 and
              all(x["branch_id"] == new_branch["id"] for x in rows(r)), str(len(rows(r))))

    s, r = call("/api/employees?hired_from=2019-01-01&hired_to=2019-12-31")
    check("  ажилд орсон огноогоор шүүх (2019 хоосон)", s == 200 and len(rows(r)) == 0, str(len(rows(r))))

    # ---- Тайлангийн төв ---------------------------------------------------- #
    print("\n── ТАЙЛАНГИЙН ТӨВ ──")
    login("manager")
    s, opt = call("/api/report-center/options")
    ok = (s == 200 and len(opt.get("reports") or []) >= 4
          and len(opt.get("branches") or []) >= 1
          and len(opt.get("tx_types") or []) == 5)
    check(f"сонголтууд ({len(opt.get('reports') or [])} тайлан, "
          f"{len(opt.get('branches') or [])} салбар)", ok, str(opt)[:100])

    year = time.strftime("%Y")
    rng = f"date_from={year}-01-01&date_to={year}-12-31"

    for code in [r["code"] for r in (opt.get("reports") or [])]:
        s, rep = call(f"/api/report-center/run?report={code}&{rng}")
        expect(f"тайлан: {code}", s, rep)

    # Олон утгатай шүүлт (давтагдах параметр)
    s, multi = call(f"/api/report-center/run?{rng}&tx_type=sale&tx_type=inbound&group_by=tx_type")
    if expect("олон утгатай шүүлт (2 төрөл)", s, multi):
        names = {r["name"] for r in multi["rows"] if r["level"] == 0}
        check("  зөвхөн сонгосон төрөл гарсан", names <= {"Борлуулалт", "Орлого"}, str(names))
        check("  шүүлтийн нөхцөл бичигдсэн", "Гүйлгээний төрөл" in multi["filter_text"],
              multi["filter_text"])

    # Шүүлтгүй үед "Бүгд"
    s, allrep = call(f"/api/report-center/run?{rng}")
    check("шүүлтгүй = Бүгд", s == 200 and allrep["filter_text"] == "Бүгд",
          str(allrep.get("filter_text")))

    # Задаргаа + гүйлгээ рүү орох
    s, det = call(f"/api/report-center/run?{rng}&include_details=true&group_by=tx_type")
    if expect("задаргаатай тайлан", s, det):
        seen = set()
        for row in det["rows"]:
            for d_row in row["details"]:
                st, sid = d_row["source_type"], d_row["source_id"]
                if not sid or st in seen:
                    continue
                seen.add(st)
                s2, tx = call(f"/api/transactions/{st}/{sid}")
                ok_tx = s2 == 200 and tx.get("title") and isinstance(tx.get("lines"), list)
                check(f"  гүйлгээ рүү орох: {st}", ok_tx, str(tx)[:100])
        check(f"  {len(seen)} төрлийн гүйлгээ шалгагдсан", len(seen) >= 3, str(seen))

    # Мөр дээр давхар товшиход гарах задаргаа
    s, grouped = call(f"/api/report-center/run?{rng}&group_by=tx_type&group_by=account")
    if expect("тайлан (зам гаргах)", s, grouped) and grouped["rows"]:
        check("  мөр бүр зам агуулсан",
              all(isinstance(r.get("path"), list) and r["path"] for r in grouped["rows"]),
              str(grouped["rows"][0])[:100])

        # Дэд түвшний мөрийн задаргаа
        leaf = next((r for r in grouped["rows"] if r["level"] == 1), None)
        if leaf:
            q = "&".join(f"path={urllib.parse.quote(p)}" for p in leaf["path"])
            s, drill = call(f"/api/report-center/drill?{rng}&group_by=tx_type&group_by=account&{q}")
            if expect(f"  задаргаа: {leaf['name']}", s, drill):
                check(f"    {drill['total']} гүйлгээ", drill["total"] > 0, str(drill["total"]))
                check("    дүн мөртэй тэнцсэн",
                      drill["totals"]["amount"] == leaf["amount"],
                      f"{drill['totals']['amount']} ≠ {leaf['amount']}")
                check("    гүйлгээ рүү орох түлхүүртэй",
                      all(x.get("source_type") for x in drill["items"]), "")

        # Дээд түвшний мөр — бүх дэд гүйлгээг хамарна
        top = next((r for r in grouped["rows"] if r["level"] == 0), None)
        if top:
            q = "&".join(f"path={urllib.parse.quote(p)}" for p in top["path"])
            s, drill = call(f"/api/report-center/drill?{rng}&group_by=tx_type&group_by=account&{q}")
            if expect(f"  задаргаа: {top['name']} (дээд түвшин)", s, drill):
                check("    дүн мөртэй тэнцсэн",
                      drill["totals"]["amount"] == top["amount"],
                      f"{drill['totals']['amount']} ≠ {top['amount']}")

    # Excel
    s, blob = download(f"/api/report-center/run.xlsx?{rng}&include_details=true")
    check(f"Excel: тайлангийн төв ({len(blob):,} байт)",
          s == 200 and blob[:2] == b"PK", str(blob[:120]))

    # ---- НББ -------------------------------------------------------------- #
    print("\n── НЯГТЛАН БОДОХ БҮРТГЭЛ ──")
    login("owner")
    for path, label in [
        ("/api/dashboards/owner", "эзний самбар"),
        (f"/api/accounting/statements/pnl?{rng}", "орлого зардлын тайлан"),
        ("/api/accounting/statements/balance-sheet", "баланс"),
        (f"/api/accounting/statements/cash-flow?{rng}", "мөнгөн урсгал"),
        ("/api/accounting/statements/inventory-valuation", "нөөцийн үнэлгээ"),
        ("/api/accounting/journal", "ерөнхий журнал"),
        ("/api/audit-logs", "аудит лог"),
        ("/api/backups", "нөөцлөлтийн жагсаалт"),
    ]:
        s, r = call(path)
        expect(label, s, r)

    s, tb = call("/api/accounting/trial-balance")
    if expect("шалгах баланс", s, tb):
        check(f"журнал тэнцсэн (зөрүү {tb['imbalance']})", d(tb["imbalance"]) == 0, str(tb["imbalance"]))

    s, bs = call("/api/accounting/statements/balance-sheet")
    if s == 200:
        check("баланс тэнцсэн", bool(bs.get("is_balanced")), str(bs.get("difference")))

    s, ig = call("/api/accounting/integrity")
    if s == 200:
        checks = ig["checks"] if isinstance(ig, dict) and "checks" in ig else ig
        for c in checks:
            note = " (бөөрөнхийлөлт)" if c.get("is_rounding") else ""
            check(f"  {c['name']}{note}", c["ok"], f"зөрүү={c.get('difference')}")

    # ---- Дүгнэлт ---------------------------------------------------------- #
    passed = sum(1 for ok, _, _ in _results if ok)
    failed = len(_results) - passed
    print(f"\n{'=' * 66}")
    print(f"  Нийт {len(_results)} шалгалт — амжилттай {passed}, алдаатай {failed}")
    print(f"{'=' * 66}")
    if failed:
        print("\nАлдаатай:")
        for ok, label, detail in _results:
            if not ok:
                print(f"  {BAD} {label}\n      {detail[:250]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
