import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Banknote,
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  CreditCard,
  Droplets,
  FileText,
  Gauge,
  HandCoins,
  Package,
  Plus,
  Scale,
  Tag,
  Trash2,
  Wallet,
} from "lucide-react";

import { errorMessage } from "../../api/client";
import { useExpenseCategories } from "../../api/queries/expenses";
import { useCustomers } from "../../api/queries/partners";
import { useProducts } from "../../api/queries/products";
import { usePumps } from "../../api/queries/pumps";
import {
  useAddPriceMarkMutation,
  useCurrentShift,
  useDailyCloseMutation,
  useDailyPreviewMutation,
  useOpenShiftMutation,
  usePriceMarks,
  useShiftAttachments,
  useUploadShiftPhotoMutation,
} from "../../api/queries/shifts";
import type {
  ArPaymentLineInput,
  CreditLineInput,
  DailyPreview,
  ExpenseLineInput,
  LitersStr,
  MoneyStr,
  OilLineInput,
  ShiftReport,
  TotalizerReadingInput,
  UUID,
} from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { dAdd, dMul, dSum, dToQty } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, PickerField, TextField } from "../catalog/_shared";

/** Литрийн утгыг байгаагаар нь (3 орон) хадгална. */
function litersOf(value: string | null | undefined): LitersStr {
  const raw = (value ?? "").trim();
  return raw === "" ? "0" : raw;
}

// --------------------------------------------------------------------------
// Зураг хавсаргах товч — сонгомогц серверт илгээнэ (ээлж нээгдсэн үед).
// --------------------------------------------------------------------------
function PhotoButton({
  shiftId,
  kind,
  queue,
}: {
  shiftId: UUID | null;
  kind: string;
  /** Ээлж хараахан нээгдээгүй үед файлуудыг энд дарааллуулна. */
  queue?: React.MutableRefObject<File[]>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadShiftPhotoMutation();
  const { data: attachments } = useShiftAttachments(shiftId);
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const [queued, setQueued] = useState(0);

  const count =
    (attachments ?? []).filter((a) => a.kind === kind).length + (shiftId ? 0 : queued);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,.pdf"
        capture="environment"
        multiple
        className="hidden"
        onChange={(event) => {
          const files = [...(event.target.files ?? [])];
          event.target.value = "";
          if (files.length === 0) return;
          if (shiftId === null) {
            queue?.current.push(...files);
            setQueued((n) => n + files.length);
            return;
          }
          for (const file of files) {
            upload.mutate(
              { shiftId, kind, file },
              {
                onSuccess: () => toastSuccess(`1 ${t.attendant.photoUploaded}`),
                onError: (cause) => toastError(errorMessage(cause)),
              },
            );
          }
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="flex h-12 items-center gap-2 rounded-xl border-2 border-dashed border-action px-4 text-[15px] font-bold text-action-dark transition-colors hover:bg-action-soft/40 active:bg-action-soft"
      >
        <Camera className="h-5 w-5" />
        {t.attendant.addPhoto}
        {count > 0 ? (
          <span className="num rounded-full bg-action px-2 py-0.5 text-xs font-bold text-white">
            {count}
          </span>
        ) : null}
      </button>
    </>
  );
}

// --------------------------------------------------------------------------
// Үнийн өөрчлөлтийн тэмдэглэл
// --------------------------------------------------------------------------
function PriceMarkModal({
  shiftId,
  open,
  onClose,
}: {
  shiftId: UUID;
  open: boolean;
  onClose: () => void;
}) {
  const { data: pumpsPage } = usePumps({ active_only: true });
  const addMark = useAddPriceMarkMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const nozzleOptions = useMemo(
    () =>
      (pumpsPage?.items ?? []).flatMap((pump) =>
        pump.nozzles.map((nozzle) => ({
          value: nozzle.id,
          label: `${pump.name} · №${nozzle.nozzle_number} ${nozzle.fuel_name}`,
        })),
      ),
    [pumpsPage],
  );

  const [nozzleId, setNozzleId] = useState("");
  const [reading, setReading] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setNozzleId(nozzleOptions[0]?.value ?? "");
    setReading("");
    setNewPrice("");
    setError(null);
  }, [open, nozzleOptions]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.attendant.priceMarkTitle}
      subtitle={t.attendant.priceMarkHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            disabled={nozzleId === "" || dToQty(reading) <= 0 || dToQty(newPrice) <= 0}
            loading={addMark.isPending}
            onClick={() =>
              addMark.mutate(
                {
                  shiftId,
                  payload: { nozzle_id: nozzleId, reading, new_price: newPrice },
                },
                {
                  onSuccess: () => {
                    toastSuccess(t.attendant.markSaved);
                    onClose();
                  },
                  onError: (cause) => setError(errorMessage(cause)),
                },
              )
            }
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField
          label={t.pos.selectNozzle}
          value={nozzleId}
          options={nozzleOptions}
          onChange={setNozzleId}
        />
        <NumberField
          name="mark-reading"
          label={t.attendant.markReading}
          value={reading}
          onChange={setReading}
          maxDecimals={3}
        />
        <NumberField
          name="mark-price"
          label={t.attendant.newPrice}
          value={newPrice}
          onChange={setNewPrice}
          suffix={t.units.mnt}
        />
        <div className="flex">
          <PhotoButton shiftId={shiftId} kind="price_mark" />
        </div>
        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Түгээгчийн ээлж — үндсэн хуудас
// --------------------------------------------------------------------------
type WizardStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

const STEP_META: { label: string; icon: typeof Gauge }[] = [
  { label: t.attendant.stepMiles, icon: Gauge },
  { label: t.attendant.stepCash, icon: Banknote },
  { label: t.attendant.stepSettlement, icon: CreditCard },
  { label: t.attendant.stepOil, icon: Package },
  { label: t.attendant.stepCredit, icon: FileText },
  { label: t.attendant.stepAr, icon: HandCoins },
  { label: t.attendant.stepExpense, icon: Wallet },
  { label: t.attendant.stepConfirm, icon: Scale },
];

interface OilRow extends OilLineInput {
  key: number;
}

interface CreditRow {
  key: number;
  contract_id: string;
  fuel_id: string;
  mode: "liters" | "amount";
  value: string;
  product_id: string;
  product_qty: string;
}

interface ArRow extends Omit<ArPaymentLineInput, "contract_id"> {
  key: number;
  contract_id: string;
}

interface ExpenseRow extends Omit<ExpenseLineInput, "account_code"> {
  key: number;
  account_code: string;
}

let rowSeq = 0;
const nextKey = (): number => ++rowSeq;

export function AttendantShiftPage() {
  const navigate = useNavigate();
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: pumpsPage, isLoading: pumpsLoading } = usePumps({ active_only: true });
  const { data: productsPage } = useProducts({ limit: 300 });
  const { data: customersPage } = useCustomers({ q: "", active_only: true, limit: 200 });
  const expenseCategories = useExpenseCategories();

  const openMutation = useOpenShiftMutation();
  const previewMutation = useDailyPreviewMutation();
  const closeMutation = useDailyCloseMutation();
  const uploadPhoto = useUploadShiftPhotoMutation();

  const shift = current?.shift ?? null;
  const shiftId = shift?.id ?? null;
  const { data: marks } = usePriceMarks(shiftId);

  const nozzles = useMemo(
    () =>
      (pumpsPage?.items ?? []).flatMap((pump) =>
        pump.nozzles.map((nozzle) => ({ pump, nozzle })),
      ),
    [pumpsPage],
  );

  const productOptions = useMemo(
    () =>
      (productsPage?.items ?? [])
        .filter((product) => product.is_active)
        .map((product) => ({ value: product.id, label: `${product.name_mn} · ${formatMNT(product.price)}` })),
    [productsPage],
  );
  const products = useMemo(() => productsPage?.items ?? [], [productsPage]);

  const contractOptions = useMemo(
    () =>
      (customersPage?.items ?? []).flatMap((customer) =>
        customer.contracts
          .filter((contract) => contract.status === "active")
          .map((contract) => ({
            value: contract.id,
            label: `${customer.name} · ${contract.contract_no}`,
          })),
      ),
    [customersPage],
  );

  const fuelOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const { nozzle } of nozzles) {
      if (!seen.has(nozzle.fuel_id)) seen.set(nozzle.fuel_id, nozzle.fuel_name);
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label }));
  }, [nozzles]);

  const categoryOptions = useMemo(
    () => (expenseCategories.data ?? []).map((row) => ({ value: row.code, label: row.name_mn })),
    [expenseCategories.data],
  );

  // ---- Нээлтийн төлөв ----
  const [openCash, setOpenCash] = useState("");
  const [openReadings, setOpenReadings] = useState<Record<UUID, string>>({});
  const openPhotoQueue = useRef<File[]>([]);

  useEffect(() => {
    if (nozzles.length === 0) return;
    setOpenReadings((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const { nozzle } of nozzles) {
        if (next[nozzle.id] === undefined) {
          next[nozzle.id] = litersOf(nozzle.totalizer);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [nozzles]);

  // ---- Хаалтын wizard төлөв ----
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>(0);
  const [closeReadings, setCloseReadings] = useState<Record<UUID, string>>({});
  const [declaredCash, setDeclaredCash] = useState("");
  const [settlementVat, setSettlementVat] = useState("");
  const [settlementNovat, setSettlementNovat] = useState("");
  const [oilRows, setOilRows] = useState<OilRow[]>([]);
  const [creditRows, setCreditRows] = useState<CreditRow[]>([]);
  const [arRows, setArRows] = useState<ArRow[]>([]);
  const [expenseRows, setExpenseRows] = useState<ExpenseRow[]>([]);
  const [preview, setPreview] = useState<DailyPreview | null>(null);
  const [closeError, setCloseError] = useState<string | null>(null);
  const [report, setReport] = useState<ShiftReport | null>(null);

  useEffect(() => {
    if (!wizardOpen || nozzles.length === 0) return;
    setCloseReadings((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const { nozzle } of nozzles) {
        if (next[nozzle.id] === undefined) {
          next[nozzle.id] = litersOf(nozzle.totalizer);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [wizardOpen, nozzles]);

  // ---- Нээх ----
  const handleOpen = (): void => {
    const readings: TotalizerReadingInput[] = nozzles.map(({ nozzle }) => ({
      nozzle_id: nozzle.id,
      reading: litersOf(openReadings[nozzle.id]),
    }));
    openMutation.mutate(
      { opening_cash: openCash === "" ? "0" : openCash, tank_dips: [], totalizer_readings: readings },
      {
        onSuccess: (created) => {
          toastSuccess(t.attendant.openedToast);
          // Дараалалд орсон зургуудыг шинэ ээлжид хавсаргана.
          for (const file of openPhotoQueue.current.splice(0)) {
            uploadPhoto.mutate({ shiftId: created.shift.id, kind: "open", file });
          }
        },
        onError: (cause) => toastError(errorMessage(cause)),
      },
    );
  };

  // ---- Хаалтын тооцоо ----
  const settlementTotal = dAdd(
    settlementVat === "" ? "0" : settlementVat,
    settlementNovat === "" ? "0" : settlementNovat,
  );
  const oilTotal = useMemo(
    () =>
      dSum(
        oilRows.map((row) => {
          const product = products.find((p) => p.id === row.product_id);
          const unit = row.unit_price || product?.price || "0";
          return dMul(unit, dToQty(row.qty || "0"));
        }),
      ),
    [oilRows, products],
  );

  const readingsPayload = (): TotalizerReadingInput[] =>
    nozzles.map(({ nozzle }) => ({
      nozzle_id: nozzle.id,
      reading: litersOf(closeReadings[nozzle.id]),
    }));

  const goToConfirm = (): void => {
    if (!shiftId) return;
    setCloseError(null);
    previewMutation.mutate(
      { shiftId, readings: readingsPayload() },
      {
        onSuccess: (data) => {
          setPreview(data);
          setStep(7);
        },
        onError: (cause) => setCloseError(errorMessage(cause)),
      },
    );
  };

  const submitClose = (): void => {
    if (!shiftId) return;
    setCloseError(null);

    const creditLines: CreditLineInput[] = creditRows
      .filter((row) => row.contract_id !== "")
      .map((row) => ({
        contract_id: row.contract_id,
        items: [
          ...(row.fuel_id !== "" && dToQty(row.value) > 0
            ? [
                row.mode === "liters"
                  ? { fuel_id: row.fuel_id, qty: row.value }
                  : { fuel_id: row.fuel_id, amount: row.value },
              ]
            : []),
          ...(row.product_id !== "" && dToQty(row.product_qty) > 0
            ? [{ product_id: row.product_id, qty: row.product_qty }]
            : []),
        ],
      }))
      .filter((line) => line.items.length > 0);

    closeMutation.mutate(
      {
        shiftId,
        payload: {
          totalizer_readings: readingsPayload(),
          declared_cash: declaredCash === "" ? "0" : declaredCash,
          settlement_vat: settlementVat === "" ? "0" : settlementVat,
          settlement_novat: settlementNovat === "" ? "0" : settlementNovat,
          oil_lines: oilRows
            .filter((row) => row.product_id !== "" && dToQty(row.qty) > 0)
            .map(({ key: _key, ...rest }) => rest),
          credit_lines: creditLines,
          ar_payments: arRows
            .filter((row) => row.contract_id !== "" && dToQty(row.amount) > 0)
            .map(({ key: _key, ...rest }) => rest),
          expenses: expenseRows
            .filter((row) => row.account_code !== "" && dToQty(row.amount) > 0)
            .map(({ key: _key, ...rest }) => rest),
        },
      },
      {
        onSuccess: (data) => {
          toastSuccess(t.attendant.closedToast);
          setReport(data);
          setWizardOpen(false);
        },
        onError: (cause) => setCloseError(errorMessage(cause)),
      },
    );
  };

  // ------------------------------------------------------------- Ачаалж байна
  if (shiftLoading || pumpsLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  // ------------------------------------------------------------ Хаалт дууссан
  if (report) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 py-6">
        <div className="flex w-full max-w-2xl flex-col items-center gap-6 rounded-2xl border-2 border-success bg-white px-6 py-10 text-center">
          <span className="flex h-24 w-24 items-center justify-center rounded-full bg-success text-white">
            <CircleCheck className="h-12 w-12" />
          </span>
          <div className="space-y-1">
            <h1 className="text-3xl font-bold text-ink">{t.attendant.closedToast}</h1>
            <p className="num text-ink-soft">
              {t.shift.number}
              {report.shift.number} · {t.shift.overShort}: {formatMNT(report.cash.cash_over_short ?? "0")}
            </p>
          </div>
          <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
            <Button
              variant="secondary"
              size="lg"
              block
              onClick={() => navigate(`/shift/report/${report.shift.id}`)}
            >
              {t.nav.shiftReport}
            </Button>
            <Button variant="success" size="lg" block onClick={() => setReport(null)}>
              {t.common.close}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------- Ээлж нээх
  if (!shift) {
    return (
      <div className="flex flex-1 flex-col gap-4 sm:gap-6">
        <PageHeader title={t.attendant.title} subtitle={t.attendant.subtitle} />

        <div className="grid grid-cols-1 gap-4 sm:gap-5 xl:grid-cols-2">
          <Card title={t.shift.openingCash}>
            <div className="flex flex-col gap-4">
              <NumberField
                name="attendant-open-cash"
                label={t.shift.openingCash}
                value={openCash}
                onChange={setOpenCash}
                suffix={t.units.mnt}
              />
              <div className="flex flex-wrap gap-3">
                <PhotoButton shiftId={null} kind="open" queue={openPhotoQueue} />
              </div>
              <p className="text-sm text-ink-soft">{t.attendant.photoRequired}</p>
            </div>
          </Card>

          <Card title={t.attendant.openMile}>
            {/* Утсанд: шошго дээрээ, талбар бүтэн өргөнөөр — урт миль таслагдахгүй. */}
            <div className="flex flex-col divide-y divide-line">
              {nozzles.map(({ pump, nozzle }) => (
                <div
                  key={nozzle.id}
                  className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:gap-3"
                >
                  <span className="min-w-0 flex-1 text-[15px] font-semibold text-ink">
                    {pump.name} · №{nozzle.nozzle_number} {nozzle.fuel_name}
                  </span>
                  <NumberField
                    name={`open-mile-${nozzle.id}`}
                    label=""
                    value={openReadings[nozzle.id] ?? ""}
                    onChange={(value) =>
                      setOpenReadings((prev) => ({ ...prev, [nozzle.id]: value }))
                    }
                    maxDecimals={3}
                    className="w-full sm:w-52"
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Утсанд доод цэсний яг дээр тууш бар болж наалдана — дэвсгэртэй тул
            доогуур нь гүйж буй талбаруудыг дарж харагдуулахгүй. Десктопт энгийн. */}
        <div className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] z-10 -mx-4 border-t border-line bg-surface/95 px-4 py-2.5 backdrop-blur sm:-mx-6 sm:px-6 lg:static lg:mx-0 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
          <Button
            variant="success"
            size="lg"
            block
            loading={openMutation.isPending}
            onClick={handleOpen}
          >
            {t.attendant.openShift}
          </Button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------- Нээлттэй ээлж
  return (
    <div className="flex flex-1 flex-col gap-4 sm:gap-6">
      <PageHeader
        title={t.attendant.title}
        subtitle={
          <span className="num">
            {t.shift.number}
            {shift.number} · {formatDateTime(shift.opened_at)} ·{" "}
            {formatMNT(shift.opening_cash)}
          </span>
        }
        actions={
          <>
            <PriceMarkButton shiftId={shift.id} />
            <Button
              variant="success"
              size="md"
              icon={<Scale />}
              className="flex-1 sm:flex-none"
              onClick={() => {
                setWizardOpen(true);
                setStep(0);
              }}
            >
              {t.attendant.dailyClose}
            </Button>
          </>
        }
      />

      {/* Үнийн тэмдэглэлүүд */}
      {(marks ?? []).length > 0 ? (
        <Card title={t.attendant.marks}>
          <ul className="flex flex-col gap-2">
            {(marks ?? []).map((mark) => (
              <li
                key={mark.id}
                className="num flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-alt px-4 py-2.5 text-[15px]"
              >
                <Tag className="h-4 w-4 shrink-0 text-warning-dark" />
                <span className="font-semibold">
                  №{mark.nozzle_number} {mark.fuel_name}
                </span>
                <span>
                  {t.attendant.mile}: {formatNumber(mark.reading, 1)}
                </span>
                <span className="text-ink-soft">
                  {formatNumber(mark.old_price)} → <b>{formatNumber(mark.new_price)}</b>{" "}
                  {t.units.perLiter}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {/* Нээлтийн мэдээлэл */}
      <Card title={t.attendant.openMile} subtitle={t.attendant.posDisabledNote}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {nozzles.map(({ pump, nozzle }) => (
            <div
              key={nozzle.id}
              className="num flex items-baseline justify-between gap-3 rounded-xl border border-line bg-white px-3.5 py-2.5"
            >
              <span className="text-[13px] font-semibold text-ink-soft sm:text-sm">
                {pump.name} · №{nozzle.nozzle_number} {nozzle.fuel_name}
              </span>
              <span className="text-base font-bold text-ink sm:text-lg">
                {formatNumber(nozzle.totalizer, 1)}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* ---------------- Өдрийн хаалтын wizard ---------------- */}
      <Modal
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        size="lg"
        title={`${t.attendant.dailyClose} — ${STEP_META[step].label}`}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              icon={<ChevronLeft />}
              disabled={step === 0}
              onClick={() => setStep((prev) => (prev > 0 ? ((prev - 1) as WizardStep) : prev))}
            >
              {t.common.prev}
            </Button>
            {step < 6 ? (
              <Button
                variant="primary"
                size="md"
                iconRight={<ChevronRight />}
                onClick={() => setStep((prev) => (prev + 1) as WizardStep)}
              >
                {t.common.next}
              </Button>
            ) : step === 6 ? (
              <Button
                variant="primary"
                size="md"
                iconRight={<ChevronRight />}
                loading={previewMutation.isPending}
                onClick={goToConfirm}
              >
                {t.attendant.stepConfirm}
              </Button>
            ) : (
              <Button
                variant="success"
                size="md"
                icon={<Check />}
                loading={closeMutation.isPending}
                onClick={submitClose}
              >
                {t.attendant.confirmClose}
              </Button>
            )}
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {/* Алхамын заагч — утсанд нэг мөр хэвтээ гүйнэ, десктопт эвхэгдэнэ */}
          <div className="scrollbar-none -mx-1 flex gap-1.5 overflow-x-auto px-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
            {STEP_META.map((meta, index) => (
              <button
                key={meta.label}
                type="button"
                ref={index === step ? (el) => el?.scrollIntoView({ inline: "center", block: "nearest" }) : undefined}
                onClick={() => setStep(index as WizardStep)}
                className={[
                  "flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-xs font-bold whitespace-nowrap",
                  index === step
                    ? "bg-action text-white"
                    : "bg-surface-sunken text-ink-soft",
                ].join(" ")}
              >
                <meta.icon className="h-3.5 w-3.5" />
                {meta.label}
              </button>
            ))}
          </div>

          {/* 0 — Эцсийн миль */}
          {step === 0 ? (
            <div className="flex flex-col divide-y divide-line">
              {nozzles.map(({ pump, nozzle }) => (
                <div
                  key={nozzle.id}
                  className="flex flex-col gap-1.5 py-3 first:pt-0 sm:flex-row sm:items-center sm:gap-3"
                >
                  <span className="min-w-0 flex-1 text-[15px] font-semibold text-ink">
                    {pump.name} · №{nozzle.nozzle_number} {nozzle.fuel_name}
                  </span>
                  <NumberField
                    name={`close-mile-${nozzle.id}`}
                    label=""
                    value={closeReadings[nozzle.id] ?? ""}
                    onChange={(value) =>
                      setCloseReadings((prev) => ({ ...prev, [nozzle.id]: value }))
                    }
                    maxDecimals={3}
                    className="w-full sm:w-52"
                  />
                </div>
              ))}
              <div className="flex pt-3">
                <PhotoButton shiftId={shiftId} kind="close" />
              </div>
            </div>
          ) : null}

          {/* 1 — Бэлэн мөнгө */}
          {step === 1 ? (
            <NumberField
              name="close-cash"
              label={t.shift.declaredCash}
              value={declaredCash}
              onChange={setDeclaredCash}
              suffix={t.units.mnt}
            />
          ) : null}

          {/* 2 — Settlement */}
          {step === 2 ? (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-ink-soft">{t.attendant.settlementHint}</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <NumberField
                  name="settle-vat"
                  label={t.attendant.settlementVat}
                  value={settlementVat}
                  onChange={setSettlementVat}
                  suffix={t.units.mnt}
                />
                <NumberField
                  name="settle-novat"
                  label={t.attendant.settlementNovat}
                  value={settlementNovat}
                  onChange={setSettlementNovat}
                  suffix={t.units.mnt}
                />
              </div>
              <div className="num flex items-baseline justify-between rounded-xl border border-line bg-surface-alt px-4 py-3">
                <span className="text-sm font-semibold text-ink-soft">
                  {t.attendant.settlementTotal}
                </span>
                <span className="text-xl font-bold text-ink">{formatMNT(settlementTotal)}</span>
              </div>
              <div className="flex">
                <PhotoButton shiftId={shiftId} kind="settlement" />
              </div>
            </div>
          ) : null}

          {/* 3 — Тос, бараа */}
          {step === 3 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-ink-soft">{t.attendant.oilHint}</p>
              {oilRows.map((row, index) => (
                <div key={row.key} className="flex flex-wrap items-end gap-2">
                  <PickerField
                    label={t.products.product}
                    value={row.product_id}
                    options={productOptions}
                    onChange={(value) =>
                      setOilRows((prev) =>
                        prev.map((r, i) => (i === index ? { ...r, product_id: value } : r)),
                      )
                    }
                    className="min-w-[16rem] flex-1"
                  />
                  <NumberField
                    name={`oil-qty-${row.key}`}
                    label={t.common.qty}
                    value={row.qty}
                    onChange={(value) =>
                      setOilRows((prev) =>
                        prev.map((r, i) => (i === index ? { ...r, qty: value } : r)),
                      )
                    }
                    maxDecimals={3}
                    className="min-w-[9rem] flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => setOilRows((prev) => prev.filter((_, i) => i !== index))}
                    className="flex h-14 w-12 items-center justify-center rounded-xl text-danger-dark active:bg-danger-soft"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>
              ))}
              <Button
                variant="secondary"
                size="md"
                icon={<Plus />}
                onClick={() =>
                  setOilRows((prev) => [...prev, { key: nextKey(), product_id: "", qty: "" }])
                }
              >
                {t.attendant.addLine}
              </Button>
              <div className="num flex items-baseline justify-between rounded-xl border border-line bg-surface-alt px-4 py-3">
                <span className="text-sm font-semibold text-ink-soft">{t.attendant.oilSales}</span>
                <span className="text-xl font-bold text-ink">{formatMNT(oilTotal)}</span>
              </div>
            </div>
          ) : null}

          {/* 4 — Зээл */}
          {step === 4 ? (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-ink-soft">{t.attendant.creditHint}</p>
              {creditRows.map((row, index) => {
                const patch = (changes: Partial<CreditRow>): void =>
                  setCreditRows((prev) =>
                    prev.map((r, i) => (i === index ? { ...r, ...changes } : r)),
                  );
                return (
                  <div key={row.key} className="flex flex-col gap-2 rounded-xl border border-line bg-surface-alt p-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <PickerField
                        label={t.nav.customers}
                        value={row.contract_id}
                        options={contractOptions}
                        onChange={(value) => patch({ contract_id: value })}
                        className="min-w-[16rem] flex-1"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setCreditRows((prev) => prev.filter((_, i) => i !== index))
                        }
                        className="flex h-14 w-12 items-center justify-center rounded-xl text-danger-dark active:bg-danger-soft"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                    <div className="flex flex-wrap items-end gap-2">
                      <PickerField
                        label={t.sales.fuel}
                        value={row.fuel_id}
                        options={[{ value: "", label: t.common.none }, ...fuelOptions]}
                        onChange={(value) => patch({ fuel_id: value })}
                        className="min-w-[10rem]"
                      />
                      <PickerField
                        label={t.attendant.creditFuelBy}
                        value={row.mode}
                        options={[
                          { value: "liters", label: t.pos.presetLiters },
                          { value: "amount", label: t.pos.presetAmount },
                        ]}
                        onChange={(value) => patch({ mode: value as "liters" | "amount" })}
                        className="min-w-[9rem]"
                      />
                      <NumberField
                        name={`credit-val-${row.key}`}
                        label={row.mode === "liters" ? t.pos.liters : t.common.amount}
                        value={row.value}
                        onChange={(value) => patch({ value })}
                        maxDecimals={3}
                        className="min-w-[10rem] flex-1"
                      />
                    </div>
                    <div className="flex flex-wrap items-end gap-2">
                      <PickerField
                        label={`${t.products.product} (${t.common.optional})`}
                        value={row.product_id}
                        options={[{ value: "", label: t.common.none }, ...productOptions]}
                        onChange={(value) => patch({ product_id: value })}
                        className="min-w-[16rem] flex-1"
                      />
                      <NumberField
                        name={`credit-pqty-${row.key}`}
                        label={t.common.qty}
                        value={row.product_qty}
                        onChange={(value) => patch({ product_qty: value })}
                        maxDecimals={3}
                        className="min-w-[8rem] flex-1"
                      />
                    </div>
                  </div>
                );
              })}
              <Button
                variant="secondary"
                size="md"
                icon={<Plus />}
                onClick={() =>
                  setCreditRows((prev) => [
                    ...prev,
                    {
                      key: nextKey(),
                      contract_id: "",
                      fuel_id: fuelOptions[0]?.value ?? "",
                      mode: "liters",
                      value: "",
                      product_id: "",
                      product_qty: "",
                    },
                  ])
                }
              >
                {t.attendant.addLine}
              </Button>
            </div>
          ) : null}

          {/* 5 — Өглөг төлөлт */}
          {step === 5 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-ink-soft">{t.attendant.arHint}</p>
              {arRows.map((row, index) => {
                const patch = (changes: Partial<ArRow>): void =>
                  setArRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...changes } : r)));
                return (
                  <div key={row.key} className="flex flex-wrap items-end gap-2">
                    <PickerField
                      label={t.nav.customers}
                      value={row.contract_id}
                      options={contractOptions}
                      onChange={(value) => patch({ contract_id: value })}
                      className="min-w-[15rem] flex-1"
                    />
                    <NumberField
                      name={`ar-amt-${row.key}`}
                      label={t.common.amount}
                      value={row.amount}
                      onChange={(value) => patch({ amount: value })}
                      suffix={t.units.mnt}
                      className="min-w-[11rem] flex-1"
                    />
                    <PickerField
                      label={t.attendant.arMethod}
                      value={row.method}
                      options={[
                        { value: "cash", label: t.attendant.methodCash },
                        { value: "card", label: t.attendant.methodCard },
                        { value: "transfer", label: t.attendant.methodTransfer },
                      ]}
                      onChange={(value) => patch({ method: value as ArRow["method"] })}
                      className="min-w-[9rem]"
                    />
                    <button
                      type="button"
                      onClick={() => setArRows((prev) => prev.filter((_, i) => i !== index))}
                      className="flex h-14 w-12 items-center justify-center rounded-xl text-danger-dark active:bg-danger-soft"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                );
              })}
              <Button
                variant="secondary"
                size="md"
                icon={<Plus />}
                onClick={() =>
                  setArRows((prev) => [
                    ...prev,
                    { key: nextKey(), contract_id: "", amount: "", method: "cash" },
                  ])
                }
              >
                {t.attendant.addLine}
              </Button>
            </div>
          ) : null}

          {/* 6 — Зарлага */}
          {step === 6 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-ink-soft">{t.attendant.expenseHint}</p>
              {expenseRows.map((row, index) => {
                const patch = (changes: Partial<ExpenseRow>): void =>
                  setExpenseRows((prev) =>
                    prev.map((r, i) => (i === index ? { ...r, ...changes } : r)),
                  );
                return (
                  <div key={row.key} className="flex flex-wrap items-end gap-2">
                    <PickerField
                      label={t.expenses.category}
                      value={row.account_code}
                      options={categoryOptions}
                      onChange={(value) => patch({ account_code: value })}
                      className="min-w-[14rem] flex-1"
                    />
                    <NumberField
                      name={`exp-amt-${row.key}`}
                      label={t.common.amount}
                      value={row.amount}
                      onChange={(value) => patch({ amount: value })}
                      suffix={t.units.mnt}
                      className="min-w-[11rem] flex-1"
                    />
                    <PickerField
                      label={t.expenses.paymentMethod}
                      value={row.payment_method}
                      options={[
                        { value: "cash", label: t.expenses.methodCash },
                        { value: "bank", label: t.expenses.methodBank },
                      ]}
                      onChange={(value) =>
                        patch({ payment_method: value as ExpenseRow["payment_method"] })
                      }
                      className="min-w-[11rem]"
                    />
                    <TextField
                      label={t.common.note}
                      value={row.description ?? ""}
                      onChange={(value) => patch({ description: value })}
                      className="min-w-[12rem] flex-1"
                    />
                    <button
                      type="button"
                      onClick={() => setExpenseRows((prev) => prev.filter((_, i) => i !== index))}
                      className="flex h-14 w-12 items-center justify-center rounded-xl text-danger-dark active:bg-danger-soft"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                );
              })}
              <Button
                variant="secondary"
                size="md"
                icon={<Plus />}
                onClick={() =>
                  setExpenseRows((prev) => [
                    ...prev,
                    {
                      key: nextKey(),
                      account_code: categoryOptions[0]?.value ?? "",
                      amount: "",
                      payment_method: "cash",
                      description: "",
                    },
                  ])
                }
              >
                {t.attendant.addLine}
              </Button>
            </div>
          ) : null}

          {/* 7 — Тулгалт */}
          {step === 7 && preview ? (
            <div className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <StatBox
                  label={t.attendant.fuelByMile}
                  value={formatMNT(preview.fuel_total)}
                  tone="brand"
                />
                <StatBox
                  label={t.pos.liters}
                  value={formatLiters(preview.fuel_liters, 1)}
                  tone="neutral"
                />
                <StatBox
                  label={t.attendant.settlementTotal}
                  value={formatMNT(settlementTotal)}
                  tone="action"
                />
              </div>

              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="num w-full text-sm">
                  <thead className="bg-surface-alt text-left text-xs font-bold text-ink-soft uppercase">
                    <tr>
                      <th className="px-3 py-2">{t.pumps.title}</th>
                      <th className="px-3 py-2 text-right">{t.attendant.openMile}</th>
                      <th className="px-3 py-2 text-right">{t.attendant.closeMile}</th>
                      <th className="px-3 py-2 text-right">{t.pos.liters}</th>
                      <th className="px-3 py-2 text-right">{t.common.amount}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.nozzles.map((row) => (
                      <tr key={row.nozzle_id} className="border-t border-line">
                        <td className="px-3 py-2">
                          №{row.nozzle_number}
                          {row.segments.length > 1 ? (
                            <span className="ml-2 text-xs text-warning-dark">
                              {row.segments.length} {t.attendant.segments}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-right">{formatNumber(row.open_reading, 1)}</td>
                        <td className="px-3 py-2 text-right">{formatNumber(row.close_reading, 1)}</td>
                        <td className="px-3 py-2 text-right">{formatLiters(row.liters, 1)}</td>
                        <td className="px-3 py-2 text-right font-bold">{formatMNT(row.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Хүлээгдэх бэлэн мөнгөний баримжаа */}
              <div className="flex flex-col gap-1.5 rounded-xl border border-line bg-surface-alt px-4 py-3 text-[15px]">
                <Row label={t.attendant.fuelByMile} value={preview.fuel_total} />
                <Row label={`− ${t.attendant.settlementTotal}`} value={settlementTotal} negative />
                <Row
                  label={`− ${t.attendant.creditSales}`}
                  value={dSum(
                    creditRows
                      .filter((row) => row.mode === "amount")
                      .map((row) => row.value || "0"),
                  )}
                  negative
                  approx
                />
                <Row label={`+ ${t.attendant.oilSales}`} value={oilTotal} />
                <Row
                  label={`+ ${t.attendant.stepAr} (${t.attendant.methodCash})`}
                  value={dSum(
                    arRows.filter((row) => row.method === "cash").map((row) => row.amount || "0"),
                  )}
                />
                <Row
                  label={`− ${t.attendant.stepExpense} (${t.expenses.methodCash})`}
                  value={dSum(
                    expenseRows
                      .filter((row) => row.payment_method === "cash")
                      .map((row) => row.amount || "0"),
                  )}
                  negative
                />
                <div className="mt-1 flex items-baseline justify-between border-t border-line-strong pt-2">
                  <span className="font-bold text-ink">{t.shift.declaredCash}</span>
                  <span className="num text-xl font-black text-ink">
                    {formatMNT(declaredCash === "" ? "0" : declaredCash)}
                  </span>
                </div>
              </div>
              <p className="text-xs text-ink-soft">
                {t.attendant.reconciliation} — {t.shift.expectedCash} серверт эцэслэн бодогдоно.
              </p>
            </div>
          ) : null}

          {closeError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {closeError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

function Row({
  label,
  value,
  negative = false,
  approx = false,
}: {
  label: string;
  value: MoneyStr;
  negative?: boolean;
  approx?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-ink-soft">
        {label}
        {approx ? " ≈" : ""}
      </span>
      <span className={`num font-semibold ${negative ? "text-danger-dark" : "text-ink"}`}>
        {formatMNT(value)}
      </span>
    </div>
  );
}

/** «Үнэ өөрчлөгдсөн» товч + цонх. */
function PriceMarkButton({ shiftId }: { shiftId: UUID }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="warning"
        size="md"
        icon={<Droplets />}
        className="flex-1 sm:flex-none"
        onClick={() => setOpen(true)}
      >
        {t.attendant.priceMark}
      </Button>
      <PriceMarkModal shiftId={shiftId} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export default AttendantShiftPage;
