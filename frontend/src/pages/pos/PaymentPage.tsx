import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, CircleCheck, Fuel, Package, Printer, Search } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useCustomers } from "../../api/queries/partners";
import { useCreateSaleMutation } from "../../api/queries/sales";
import type {
  ContractBrief,
  Customer,
  MoneyStr,
  PaymentInput,
  PaymentMethod,
  SaleCreate,
  SaleCreatedResponse,
  SaleItemInput,
  SaleType,
} from "../../api/types";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { SplitTenderList, type TenderLine } from "../../components/pos/SplitTenderList";
import { TenderPad } from "../../components/pos/TenderPad";
import { ReceiptTemplate } from "../../components/receipt/ReceiptTemplate";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { usePrint } from "../../hooks/usePrint";
import { t } from "../../i18n/mn";
import { QUICK_CASH, TENDER_BY_METHOD, TENDER_METHODS, colors } from "../../lib/constants";
import {
  D_ZERO,
  dAbs,
  dAdd,
  dCmp,
  dDiv,
  dIsZero,
  dMax,
  dMin,
  dMul,
  dSub,
  dSum,
  dToQty,
  toDisplay,
} from "../../lib/decimal";
import { formatLiters, formatMNT, formatQty } from "../../lib/format";
import { useBranchPaymentMethods } from "../../api/queries/branches";
import { useAuthStore } from "../../stores/auth";
import { useCartStore } from "../../stores/cart";
import { useFuelSaleStore } from "../../stores/fuelSale";
import { useUiStore } from "../../stores/ui";

const PAD_AMOUNT = "tender.amount:";
const PAD_RECEIVED = "tender.received:";
const PAD_REF = "tender.ref:";

let tenderSeq = 0;
function nextTenderId(): string {
  tenderSeq += 1;
  return `tender-${tenderSeq}`;
}

function blankLine(method: PaymentMethod, amount: MoneyStr, manual = false): TenderLine {
  return {
    id: nextTenderId(),
    method,
    amount,
    manual,
    received: null,
    contractId: null,
    contractLabel: null,
    discountPerL: null,
    refNo: null,
  };
}

/**
 * Гараар тогтоогоогүй («авто») мөрүүдийг нийт дүнд тааруулж дахин хуваарилна.
 *
 * Дүрэм энгийн: гараар оруулсан мөрүүд хөдлөхгүй, үлдсэн төсвийг авто мөрүүд
 * дарааллаараа аваад, **хамгийн сүүлийн** авто мөр үлдэгдлийг бүхэлд нь шингээнэ.
 * Ингэснээр хоёр зүйл шийдэгдэнэ:
 *  - хосолсон төлбөрт эхний мөрийн дүнг өөрчлөхөд дараагийнх нь өөрөө бөглөгдөнө;
 *  - гэрээ сонгоход хөнгөлөлтөөр нийт дүн буурвал төлбөр «илүү» болж үлдэхгүй.
 */
function balanceTenders(lines: readonly TenderLine[], total: MoneyStr): TenderLine[] {
  const autoIndexes = lines.map((line, index) => (line.manual ? -1 : index)).filter((i) => i >= 0);
  if (autoIndexes.length === 0) return [...lines];

  const fixed = dSum(lines.filter((line) => line.manual).map((line) => line.amount));
  let budget = dMax(dSub(total, fixed), D_ZERO);

  const next = [...lines];
  autoIndexes.forEach((index, order) => {
    const last = order === autoIndexes.length - 1;
    const amount = last ? budget : dMin(next[index].amount, budget);
    next[index] = { ...next[index], amount };
    budget = dMax(dSub(budget, amount), D_ZERO);
  });
  return next;
}

/** Гэрээ сонгох цонх — `useCustomers`-ийг ашиглаж клиент талд шүүнэ. */
function ContractPicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (customer: Customer, contract: ContractBrief) => void;
}) {
  const [query, setQuery] = useState("");
  const { data, isLoading } = useCustomers({ q: query, active_only: true, limit: 200 });

  const rows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("mn-MN");
    return (data?.items ?? [])
      .filter((customer) => customer.contracts.some((contract) => contract.status === "active"))
      .filter((customer) => {
        if (needle === "") return true;
        return (
          customer.name.toLocaleLowerCase("mn-MN").includes(needle) ||
          (customer.register_no ?? "").toLocaleLowerCase("mn-MN").includes(needle) ||
          (customer.phone ?? "").includes(needle)
        );
      });
  }, [data, query]);

  return (
    <Modal open={open} onClose={onClose} size="lg" title={t.tender.selectContract}>
      <div className="flex flex-col gap-4">
        <div className="relative flex items-center">
          <Search className="pointer-events-none absolute left-4 h-5 w-5 text-ink-faint" aria-hidden="true" />
          <input
            type="search"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.common.searchPlaceholder}
            aria-label={t.common.search}
            className="h-14 w-full rounded-xl border border-line-strong bg-white pr-4 pl-12 text-base text-ink outline-none focus:border-action"
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10 text-ink-soft">
            <Spinner size="lg" label={t.common.loading} />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState title={t.common.empty} hint={t.common.emptyHint} />
        ) : (
          <ul className="flex flex-col gap-2.5">
            {rows.map((customer) =>
              customer.contracts
                .filter((contract) => contract.status === "active")
                .map((contract) => (
                  <li key={contract.id}>
                    <button
                      type="button"
                      onClick={() => onPick(customer, contract)}
                      className="flex min-h-20 w-full flex-wrap items-center gap-4 rounded-xl border border-line-strong bg-white px-4 py-3 text-left active:bg-surface-sunken"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-base font-bold text-ink">{customer.name}</span>
                        <span className="num block truncate text-sm text-ink-soft">
                          {contract.contract_no}
                          {customer.register_no ? ` · ${customer.register_no}` : ""}
                        </span>
                      </span>
                      <span className="text-right">
                        <span className="block text-xs font-semibold text-ink-soft">
                          {t.partners.creditAvailable}
                        </span>
                        <span className="num block text-lg font-bold text-success-dark">
                          {formatMNT(contract.credit_available)}
                        </span>
                      </span>
                    </button>
                  </li>
                )),
            )}
          </ul>
        )}
      </div>
    </Modal>
  );
}

export function PaymentPage() {
  const navigate = useNavigate();
  const { print, portal } = usePrint();

  // Түгээгчийн салбарт зөвшөөрсөн хэрэгслүүд (салбаргүй хэрэглэгчид бүгд).
  const branchId = useAuthStore((state) => state.user?.branch?.id) ?? null;
  const methodsQuery = useBranchPaymentMethods(branchId);
  const allowedMethods = useMemo<PaymentMethod[] | null>(() => {
    if (!branchId || !methodsQuery.data) return null;
    return methodsQuery.data
      .filter((row) => row.is_enabled)
      .map((row) => row.method as PaymentMethod);
  }, [branchId, methodsQuery.data]);

  const sale = useFuelSaleStore();
  const resetFuel = useFuelSaleStore((state) => state.reset);
  const cartLines = useCartStore((state) => state.lines);
  const cartLineTotal = useCartStore((state) => state.lineTotal);
  const cartTotal = useCartStore((state) => state.total);
  const clearCart = useCartStore((state) => state.clear);

  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastError = useUiStore((state) => state.toastError);

  const createSale = useCreateSaleMutation();

  const [rawTenders, setRawTenders] = useState<TenderLine[]>([]);
  const [pickerLineId, setPickerLineId] = useState<string | null>(null);
  const [result, setResult] = useState<SaleCreatedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // --- Идэвхтэй урсгал -----------------------------------------------------
  const fuelLiters = sale.finalLiters ?? (sale.authorizationId ? sale.liveLiters : null);
  const fuelBaseAmount = sale.finalAmount ?? (sale.authorizationId ? sale.liveAmount : null);
  // Тоолуургүй гар борлуулалтад authorization_id байхгүй — литр байхад л хангалттай.
  const hasFuel = Boolean(fuelLiters && dCmp(fuelLiters, "0") > 0);
  const hasStore = cartLines.length > 0;
  const storeTotal = hasStore ? cartTotal() : D_ZERO;

  const contractLine = rawTenders.find((line) => line.method === "contract" && line.contractId) ?? null;
  const discountPerL = contractLine?.discountPerL ?? D_ZERO;

  /**
   * Гэрээний литрийн хөнгөлөлт орсон түлшний мөр.
   *
   * Юуг тогтмол барихыг касс юугаар оруулснаас хамааруулна:
   *  - **мөнгөн дүнгээр** оруулсан бол дүн нь тогтмол — хөнгөлөлттэй үнээр
   *    илүү литр өгнө (90 000₮ гэвэл 90 000₮-ийн шатахуун);
   *  - **литрээр** оруулсан (эсвэл насосноос ирсэн) бол литр тогтмол —
   *    хөнгөлөлтөөр дүн буурна.
   *
   * Литр 3 оронтой тул `литр × үнэ` нь оруулсан дүнгээс 1-2₮ зөрж болно.
   * Мөнгөн горимд оруулсан дүнг ЯГ хэвээр барина (сервер мөн адил — мөрийн
   * `amount`-ыг 1 мл-ийн үнийн хүрээнд зөвшөөрдөг); эс бөгөөс түгээгч
   * 90 000₮ гэж бичээд 89 999₮ гэсэн баримт барьж өгнө.
   */
  const fuelLine = useMemo(() => {
    if (!hasFuel || fuelLiters === null) {
      return { liters: fuelLiters, amount: D_ZERO };
    }
    const base = toDisplay(fuelBaseAmount ?? D_ZERO);
    if (dIsZero(discountPerL) || sale.unitPrice === null) {
      return { liters: fuelLiters, amount: base };
    }

    const unitPrice = dMax(dSub(sale.unitPrice, discountPerL), D_ZERO);
    if (dCmp(unitPrice, "0") <= 0) return { liters: fuelLiters, amount: D_ZERO };

    if (sale.entryMode === "amount") {
      // Мөнгө тогтмол: хөнгөлөлттэй үнээр литрийг дахин бодно, дүн хэвээр.
      return { liters: dDiv(base, unitPrice, 3), amount: base };
    }
    // Литр тогтмол: хөнгөлөлтөөр дүн буурна.
    return { liters: fuelLiters, amount: dMul(unitPrice, dToQty(fuelLiters)) };
  }, [hasFuel, discountPerL, sale.unitPrice, sale.entryMode, fuelLiters, fuelBaseAmount]);

  const fuelQty = fuelLine.liters;
  const fuelAmount = fuelLine.amount;

  const total = dAdd(fuelAmount, storeTotal);
  // Авто мөрүүд нийт дүнгээ дагана — доорх бүх логик тэнцүүлсэн жагсаалтаар явна.
  const tenders = useMemo(() => balanceTenders(rawTenders, total), [rawTenders, total]);
  const paid = dSum(tenders.map((line) => line.amount));
  const remaining = dSub(total, paid);
  const shortfall = dMax(remaining, D_ZERO);

  const saleType: SaleType = hasFuel && hasStore ? "mixed" : hasStore ? "store" : "fuel";
  const flowEmpty = !hasFuel && !hasStore;

  // --- Үйлдэл ---------------------------------------------------------------
  const addTender = (method: PaymentMethod): void => {
    if (method === "contract" && tenders.some((line) => line.method === method)) {
      toastError(`${TENDER_BY_METHOD[method].label} — ${t.tender.tooMuch}`);
      return;
    }
    const line = blankLine(method, shortfall);
    setRawTenders((prev) => [...prev, line]);
    setError(null);
    if (method === "contract") setPickerLineId(line.id);
  };

  /**
   * Хосолсон төлбөр — үлдэгдлийг хоёр хэрэгсэлд хуваан бэлдэнэ.
   *
   * Эхнийх нь бэлэн (хариулт өгөх боломжтой), хоёр дахь нь салбарт
   * зөвшөөрөгдсөн дараагийн хэрэгсэл (ихэвчлэн карт).  Эхний мөрийн дүнг
   * (эсвэл авсан мөнгийг) өөрчлөхөд хоёр дахь нь үлдэгдлийг өөрөө авна.
   */
  const startCombined = (): void => {
    if (dCmp(shortfall, "0") <= 0) return;

    const pool = allowedMethods ?? TENDER_METHODS.map((meta) => meta.value);
    const second = pool.find((method) => method !== "cash" && method !== "contract") ?? "card";

    const half = dDiv(shortfall, "2", 2);
    setRawTenders((prev) => [
      ...prev,
      blankLine("cash", half),
      blankLine(second as PaymentMethod, dSub(shortfall, half)),
    ]);
    setError(null);
  };

  const patchLine = (id: string, patch: Partial<TenderLine>): void => {
    setRawTenders((prev) => prev.map((line) => (line.id === id ? { ...line, ...patch } : line)));
  };

  /**
   * Бэлэн мөрийн «авсан мөнгө».
   *
   * Хэрэв авсан мөнгө тухайн мөрийн дүнгээс бага бол кассаар яг төдийг нь
   * авч байна гэсэн үг — мөрийн дүн шууд түүн болж, үлдсэнийг дараагийн
   * (авто) хэрэгсэл өөрөө шингээнэ.  Их бол ердийн хариулт.
   */
  const setReceived = (line: TenderLine, value: MoneyStr | null): void => {
    if (value !== null && dCmp(value, line.amount) < 0) {
      patchLine(line.id, { received: value, amount: value, manual: true });
      return;
    }
    patchLine(line.id, { received: value });
  };

  const removeTender = (id: string): void => {
    setRawTenders((prev) => prev.filter((line) => line.id !== id));
    setError(null);
  };

  const editAmount = (line: TenderLine): void => {
    openNumPad({
      target: `${PAD_AMOUNT}${line.id}`,
      title: `${TENDER_BY_METHOD[line.method].label} — ${t.common.amount}`,
      value: line.amount,
      allowDecimal: true,
      suffix: t.units.mnt,
    });
  };

  const handleNumPad = (target: string, value: string): void => {
    const apply = (prefix: string, patch: (id: string) => void): boolean => {
      if (!target.startsWith(prefix)) return false;
      patch(target.slice(prefix.length));
      return true;
    };

    // Дүнг гараар өөрчлөх нь мөрийг «гараар тогтоосон» болгоно — үлдэгдлийг
    // дараагийн авто мөр авна.  Хуучин авсан мөнгө хүчингүй тул цэвэрлэнэ.
    if (apply(PAD_AMOUNT, (id) => patchLine(id, { amount: toDisplay(value), manual: true, received: null })))
      return;
    if (
      apply(PAD_RECEIVED, (id) => {
        const line = tenders.find((item) => item.id === id);
        if (line) setReceived(line, value === "" ? null : toDisplay(value));
      })
    )
      return;
    apply(PAD_REF, (id) => patchLine(id, { refNo: value === "" ? null : value }));
  };

  const pickContract = (customer: Customer, contract: ContractBrief): void => {
    if (!pickerLineId) return;
    patchLine(pickerLineId, {
      contractId: contract.id,
      contractLabel: `${customer.name} · ${contract.contract_no}`,
      discountPerL: contract.price_discount_per_l,
    });
    setPickerLineId(null);
  };

  // --- Дуусгах боломжтой эсэх ----------------------------------------------
  const blocker = useMemo<string | null>(() => {
    if (flowEmpty) return t.pos.cartEmpty;
    if (tenders.length === 0) return t.tender.notEnough;
    for (const line of tenders) {
      if (dCmp(line.amount, "0") <= 0) return t.tender.notEnough;
      if (line.method === "contract" && !line.contractId) return t.tender.selectContract;
      if (line.method === "cash" && line.received !== null && dCmp(line.received, line.amount) < 0) {
        return `${t.tender.notEnough} · ${formatMNT(dSub(line.amount, line.received))}`;
      }
    }
    // Дутуу/илүү дүнг тоогоор нь хамт харуулна — түгээгч хэдийг засахаа шууд мэднэ.
    if (!dIsZero(remaining)) {
      return dCmp(remaining, "0") > 0
        ? `${t.tender.notEnough} · ${t.tender.shortBy} ${formatMNT(remaining)}`
        : `${t.tender.overpaid} · ${formatMNT(dAbs(remaining))}`;
    }
    return null;
  }, [flowEmpty, tenders, remaining]);

  const handleComplete = (): void => {
    if (blocker !== null) return;

    const items: SaleItemInput[] = [];
    if (hasFuel && fuelQty !== null) {
      items.push({
        item_type: "fuel",
        fuel_id: sale.fuelId,
        tank_id: sale.tankId,
        pump_id: sale.pumpId,
        nozzle_id: sale.nozzleId,
        product_id: null,
        qty: fuelQty,
        // Гар бүртгэлд бөөрөнхийлөлтөөс болж дүн хазайхаас сэргийлж нэгж үнэ,
        // мөнгөн дүнг мөрөөс нь буцааж илгээнэ (насосны бичлэг байхгүй үед).
        unit_price: sale.authorizationId === null ? sale.unitPrice : null,
        amount: sale.authorizationId === null ? fuelAmount : null,
        authorization_id: sale.authorizationId,
      });
    }
    for (const line of cartLines) {
      items.push({
        item_type: "product",
        product_id: line.productId,
        qty: String(line.qty),
        unit_price: line.unitPrice,
        // Задлан зарсан мөрд кассын оруулсан яг дүнг барина.
        amount: line.amount,
        authorization_id: null,
      });
    }

    const payments: PaymentInput[] = tenders.map((line) => ({
      method: line.method,
      amount: line.amount,
      contract_id: line.contractId,
      received: line.method === "cash" ? line.received : null,
      ref_no: line.refNo,
    }));

    const payload: SaleCreate = {
      sale_type: saleType,
      items,
      payments,
      contract_id: contractLine?.contractId ?? null,
    };

    setError(null);
    createSale.mutate(payload, {
      onSuccess: (data) => {
        setResult(data);
        setRawTenders([]);
        resetFuel();
        clearCart();
      },
      onError: (cause) => {
        const message = errorMessage(cause);
        setError(message);
        toastError(message);
      },
    });
  };

  const startNewSale = (): void => {
    setResult(null);
    setRawTenders([]);
    resetFuel();
    clearCart();
    navigate(saleType === "store" ? "/pos/store" : "/pos");
  };

  // ------------------------------------------------------------ Амжилттай
  if (result) {
    const change = result.sale.change_total;
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 py-6">
        <div className="flex w-full max-w-2xl flex-col items-center gap-6 rounded-2xl border-2 border-success bg-white px-6 py-10 text-center">
          <span className="flex h-24 w-24 items-center justify-center rounded-full bg-success text-white">
            <CircleCheck className="h-12 w-12" />
          </span>

          <div className="space-y-1">
            <h1 className="text-3xl font-bold text-ink">{t.pos.saleComplete}</h1>
            <p className="num text-ink-soft">
              {t.sales.saleNo} {result.sale.number} · {formatMNT(result.sale.total)}
            </p>
          </div>

          {dCmp(change, "0") > 0 ? (
            <div className="w-full rounded-2xl border-2 border-warning bg-warning-soft px-6 py-5">
              <div className="text-sm font-bold tracking-wide text-warning-dark uppercase">
                {t.tender.change}
              </div>
              <div className="num mt-1 text-[56px] leading-none font-black text-warning-dark">
                {formatMNT(change)}
              </div>
            </div>
          ) : null}

          {result.sale.ebarimt ? (
            <div className="num text-sm text-ink-soft">
              {t.sales.ebarimt}: {result.sale.ebarimt.status_name}
              {result.sale.ebarimt.lottery_no ? ` · ${result.sale.ebarimt.lottery_no}` : ""}
            </div>
          ) : null}

          <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
            <Button
              variant="secondary"
              size="lg"
              block
              icon={<Printer />}
              onClick={() => print(<ReceiptTemplate receipt={result.receipt} />)}
            >
              {t.pos.printReceipt}
            </Button>
            <Button variant="success" size="lg" block onClick={startNewSale}>
              {t.pos.newSale}
            </Button>
          </div>
        </div>
        {portal}
      </div>
    );
  }

  // ------------------------------------------------------------- Урсгал алга
  if (flowEmpty) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <div className="flex flex-1 items-center justify-center">
          <EmptyState
            title={t.pos.cartEmpty}
            hint={t.pos.newSale}
            action={
              <div className="flex flex-wrap justify-center gap-3">
                <Button variant="primary" size="lg" icon={<Fuel />} onClick={() => navigate("/pos")}>
                  {t.pos.forecourt}
                </Button>
                <Button variant="secondary" size="lg" icon={<Package />} onClick={() => navigate("/pos/store")}>
                  {t.pos.store}
                </Button>
              </div>
            }
          />
        </div>
      </div>
    );
  }

  // ----------------------------------------------------------------- Төлбөр
  return (
    <div className="flex flex-1 flex-col gap-5">
      {/* Толгой + нийт дүн */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => navigate(hasStore && !hasFuel ? "/pos/store" : "/pos")}
          className="flex h-12 items-center gap-2 rounded-xl border border-line-strong bg-white px-4 font-semibold text-ink active:bg-surface-sunken"
        >
          <ChevronLeft className="h-5 w-5" />
          {t.common.back}
        </button>
        <h1 className="flex-1 text-2xl font-bold text-ink">{t.nav.payment}</h1>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl bg-brand-900 px-6 py-5 text-ink-invert">
        <div>
          <div className="text-sm font-semibold tracking-widest text-slate-400 uppercase">
            {t.pos.totalDue}
          </div>
          <div className="num mt-1 text-[clamp(40px,9vw,64px)] leading-none font-black text-white">
            {formatMNT(total)}
          </div>
        </div>

        <ul className="flex flex-col gap-1 text-right text-sm text-slate-300">
          {hasFuel ? (
            <li className="num">
              {sale.fuelName ?? t.sales.fuel} · {formatLiters(fuelQty, 2)} → {formatMNT(fuelAmount)}
            </li>
          ) : null}
          {cartLines.map((line) => (
            <li key={line.productId} className="num truncate">
              {line.name} × {formatQty(line.qty)} → {formatMNT(cartLineTotal(line))}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <TenderPad
          onPick={addTender}
          onSplit={startCombined}
          allowed={allowedMethods}
          used={tenders.map((line) => line.method)}
          disabled={createSale.isPending}
        />

        <div className="flex flex-col gap-5">
          <SplitTenderList
            lines={tenders}
            remaining={remaining}
            onEditAmount={editAmount}
            onRemove={removeTender}
            renderDetail={(line) => {
              if (line.method === "cash") {
                // Авсан мөнгө оруулаагүй бол мөрийн дүнгээрээ яг таарч байна гэсэн үг.
                const received = line.received;
                const shown = received ?? line.amount;
                const change = dMax(dSub(shown, line.amount), D_ZERO);
                return (
                  <div className="flex flex-col gap-3">
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        type="button"
                        // «Тэгш» — мөрийг дахин авто болгож үлдэгдлийг бүхэлд нь авна.
                        onClick={() => patchLine(line.id, { received: null, manual: false })}
                        className="num h-12 rounded-xl border border-success/30 bg-success-soft text-sm font-bold text-success-dark active:bg-success/20"
                      >
                        {t.tender.exact}
                      </button>
                      {QUICK_CASH.slice(1).map((quick) => (
                        <button
                          key={quick}
                          type="button"
                          onClick={() => setReceived(line, toDisplay(quick))}
                          className="num h-12 rounded-xl border border-action/25 bg-action-soft text-sm font-bold text-action-dark active:bg-action/20"
                        >
                          {formatMNT(quick)}
                        </button>
                      ))}
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <button
                        type="button"
                        onClick={() =>
                          openNumPad({
                            target: `${PAD_RECEIVED}${line.id}`,
                            title: t.tender.received,
                            value: line.received ?? "",
                            allowDecimal: true,
                            suffix: t.units.mnt,
                          })
                        }
                        className="flex min-h-14 flex-col justify-center rounded-xl border border-line-strong bg-surface-alt px-4 text-left active:bg-surface-sunken"
                      >
                        <span className="text-xs font-semibold text-ink-soft">{t.tender.received}</span>
                        <span
                          className={`num text-xl font-bold ${received === null ? "text-ink-soft" : "text-ink"}`}
                        >
                          {formatMNT(shown)}
                        </span>
                      </button>

                      <div className="flex min-h-14 flex-col justify-center rounded-xl border border-line-strong bg-white px-4">
                        <span className="text-xs font-semibold text-ink-soft">{t.tender.change}</span>
                        <span className="num text-xl font-bold text-success-dark">{formatMNT(change)}</span>
                      </div>
                    </div>
                  </div>
                );
              }

              if (line.method === "contract") {
                return (
                  <div className="flex flex-col gap-3">
                    <button
                      type="button"
                      onClick={() => setPickerLineId(line.id)}
                      className="flex min-h-14 items-center gap-3 rounded-xl border border-line-strong bg-surface-alt px-4 text-left active:bg-surface-sunken"
                    >
                      <Search className="h-5 w-5 shrink-0 text-ink-faint" />
                      <span className="min-w-0 flex-1 truncate text-base font-bold text-ink">
                        {line.contractLabel ?? t.tender.selectContract}
                      </span>
                    </button>
                    {line.contractId ? (
                      <ContractCredit contractId={line.contractId} amount={line.amount} />
                    ) : null}
                  </div>
                );
              }

              // Карт / QR / шилжүүлэг — гүйлгээний дугаар (заавал биш)
              return (
                <button
                  type="button"
                  onClick={() =>
                    openNumPad({
                      target: `${PAD_REF}${line.id}`,
                      title: t.tender.refNo,
                      value: line.refNo ?? "",
                      allowDecimal: false,
                      suffix: "",
                    })
                  }
                  className="flex min-h-14 w-full items-center gap-3 rounded-xl border border-line-strong bg-surface-alt px-4 text-left active:bg-surface-sunken"
                >
                  <span className="text-xs font-semibold text-ink-soft">{t.tender.refNo}</span>
                  <span className="num min-w-0 flex-1 truncate text-base font-bold text-ink">
                    {line.refNo ?? t.common.optional}
                  </span>
                </button>
              );
            }}
          />

          {error ? (
            <div className="rounded-xl border border-danger bg-danger-soft px-4 py-3 text-[15px] font-semibold text-danger-dark">
              {error}
            </div>
          ) : null}

          {blocker !== null && tenders.length > 0 ? (
            <div className="text-center text-sm font-semibold text-warning-dark">{blocker}</div>
          ) : null}

          <Button
            variant="success"
            size="lg"
            block
            disabled={blocker !== null}
            loading={createSale.isPending}
            onClick={handleComplete}
          >
            {t.tender.complete}
          </Button>
        </div>
      </div>

      <ContractPicker
        open={pickerLineId !== null}
        onClose={() => setPickerLineId(null)}
        onPick={pickContract}
      />

      <NumPadModal
        onSubmit={handleNumPad}
        quickFor={(target) => (target.startsWith(PAD_RECEIVED) ? QUICK_CASH : undefined)}
      />

      {portal}
    </div>
  );
}

/** Гэрээний зээлийн хязгаар ба боломжит үлдэгдэл. */
function ContractCredit({ contractId, amount }: { contractId: string; amount: MoneyStr }) {
  // Гэрээ сонгох цонхтой ижил query key — давхар хүсэлт явуулахгүй.
  const { data } = useCustomers({ q: "", active_only: true, limit: 200 });
  const contract = useMemo(() => {
    for (const customer of data?.items ?? []) {
      const hit = customer.contracts.find((item) => item.id === contractId);
      if (hit) return hit;
    }
    return null;
  }, [data, contractId]);

  if (!contract) return null;
  const enough = dCmp(contract.credit_available, amount) >= 0;

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="rounded-xl border border-line-strong bg-white px-4 py-2.5">
        <div className="text-xs font-semibold text-ink-soft">{t.partners.creditLimit}</div>
        <div className="num text-lg font-bold text-ink">{formatMNT(contract.credit_limit)}</div>
      </div>
      <div
        className="rounded-xl border px-4 py-2.5"
        style={{
          borderColor: enough ? colors.success : colors.danger,
          backgroundColor: enough ? "#ECFDF5" : "#FEF2F2",
        }}
      >
        <div className="text-xs font-semibold text-ink-soft">{t.partners.creditAvailable}</div>
        <div className={`num text-lg font-bold ${enough ? "text-success-dark" : "text-danger-dark"}`}>
          {formatMNT(contract.credit_available)}
        </div>
      </div>
    </div>
  );
}

export default PaymentPage;
