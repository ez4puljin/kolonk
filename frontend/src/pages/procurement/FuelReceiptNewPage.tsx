import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Save } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import { useCreateFuelReceiptMutation, useSuppliers } from "../../api/queries/procurement";
import { useSettings } from "../../api/queries/system";
import { useTanks } from "../../api/queries/tanks";
import type { Tank } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { t } from "../../i18n/mn";
import { dAdd, dMul, dToNumber, dToQty } from "../../lib/decimal";
import { formatLiters, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, FieldLabel, NumberField, PickerField, TextAreaField, TextField } from "../catalog/_shared";

const DEFAULT_VAT_RATE = 0.1;

/** Тохиргооноос НӨАТ-ын хувь (жишээ "0.10"). Зөвхөн итгэлцүүр — мөнгө биш. */
function vatRateOf(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed >= 0 && parsed < 1) return parsed;
  }
  return DEFAULT_VAT_RATE;
}

/** Савны карт — аль салбарын аль саванд буулгахаа нэг харцаар сонгоно. */
function TankCard({
  tank,
  selected,
  incomingL,
  onSelect,
}: {
  tank: Tank;
  selected: boolean;
  incomingL: number;
  onSelect: () => void;
}) {
  const capacity = dToNumber(tank.capacity_l);
  const current = dToNumber(tank.current_l);
  const after = current + (selected ? incomingL : 0);
  const overCapacity = selected && capacity > 0 && after > capacity;
  const pct = capacity > 0 ? Math.min(100, (after / capacity) * 100) : 0;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "flex min-w-0 flex-col gap-2 rounded-xl border-2 px-4 py-3 text-left transition-colors",
        selected
          ? overCapacity
            ? "border-danger bg-danger-soft/40"
            : "border-action bg-action-soft/40"
          : "border-line bg-white hover:bg-surface-alt",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span
            className="h-3 w-3 shrink-0 rounded-full"
            style={{ backgroundColor: tank.fuel.color_hex }}
          />
          <span className="truncate font-bold text-ink">{tank.name}</span>
        </span>
        {selected ? <Check className="h-5 w-5 shrink-0 text-action" /> : null}
      </div>
      <span className="text-sm text-ink-soft">{tank.fuel.name_mn}</span>
      <ProgressBar value={pct} tone={overCapacity ? "danger" : pct > 90 ? "warning" : "success"} />
      <span className="num text-xs text-ink-soft">
        {formatLiters(tank.current_l, 0)} / {formatLiters(tank.capacity_l, 0)}
        {selected && incomingL > 0 ? (
          <b className={overCapacity ? "text-danger-dark" : "text-success-dark"}>
            {" "}
            → {formatLiters(String(after), 0)}
          </b>
        ) : null}
      </span>
    </button>
  );
}

export function FuelReceiptNewPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const tanksQuery = useTanks({ active_only: true });
  const branchesQuery = useBranches();
  const settingsQuery = useSettings();
  const createMutation = useCreateFuelReceiptMutation();

  const [branchFilter, setBranchFilter] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [tankId, setTankId] = useState("");
  const [receiptDate, setReceiptDate] = useState(todayInput());
  const [invoiceNo, setInvoiceNo] = useState("");
  const [liters, setLiters] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [freight, setFreight] = useState("");
  const [showExtra, setShowExtra] = useState(false);
  const [density, setDensity] = useState("");
  const [temperature, setTemperature] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const tanks = useMemo(() => tanksQuery.data?.items ?? [], [tanksQuery.data]);
  const tank = tanks.find((item) => item.id === tankId) ?? null;

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const multiBranch = branches.length > 1;

  /** Салбарын шүүлтэд тохирох савнууд (нэг салбартай бол бүгд). */
  const visibleTanks = useMemo(
    () => (branchFilter === "" ? tanks : tanks.filter((item) => item.branch_id === branchFilter)),
    [tanks, branchFilter],
  );

  const vatRate = vatRateOf(settingsQuery.data?.vat_rate);

  const litersNum = dToQty(liters);
  const goodsAmount = dMul(unitCost, litersNum);
  const subtotal = dAdd(goodsAmount, freight);
  const vatAmount = dMul(subtotal, vatRate);
  const totalGross = dAdd(subtotal, vatAmount);
  const landedUnitCost = litersNum > 0 ? dMul(subtotal, 1 / litersNum) : "0.00";

  const overCapacity =
    tank !== null && dToNumber(tank.capacity_l) > 0
      ? dToNumber(tank.current_l) + litersNum > dToNumber(tank.capacity_l)
      : false;

  const canSubmit =
    supplierId !== "" && tankId !== "" && litersNum > 0 && dToNumber(unitCost) > 0 && !overCapacity;

  const submit = (): void => {
    if (!canSubmit || !tank) return;
    setError(null);
    createMutation.mutate(
      {
        supplier_id: supplierId,
        tank_id: tankId,
        fuel_id: tank.fuel_id,
        receipt_date: receiptDate,
        invoice_no: invoiceNo.trim() || null,
        liters,
        unit_cost: unitCost,
        freight_cost: freight === "" ? "0" : freight,
        density: density === "" ? null : density,
        temperature_c: temperature === "" ? null : temperature,
        note: note.trim() || null,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          navigate("/receipts/fuel");
        },
        onError: (mutationError) => setError(errorMessage(mutationError)),
      },
    );
  };

  const supplierOptions = useMemo(
    () =>
      (suppliersQuery.data?.items ?? [])
        .filter((supplier) => supplier.is_active)
        .map((supplier) => ({
          value: supplier.id,
          label: supplier.name,
          hint: supplier.register_no ?? undefined,
        })),
    [suppliersQuery.data],
  );

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.procurement.newFuelReceipt} back="/receipts/fuel" />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-6">
          {/* 1. Аль салбарын аль саванд буулгах вэ */}
          <Card title={t.tanks.tank}>
            <div className="flex flex-col gap-3">
              {multiBranch ? (
                <div className="flex flex-col gap-1.5">
                  <FieldLabel>{t.branches.title}</FieldLabel>
                  <div className="flex flex-wrap gap-2">
                    {[{ id: "", name: t.branches.allBranches }, ...branches].map((branch) => {
                      const active = branchFilter === branch.id;
                      return (
                        <button
                          key={branch.id || "all"}
                          type="button"
                          onClick={() => setBranchFilter(branch.id)}
                          className={[
                            "flex h-12 items-center rounded-xl border px-4 text-[15px] font-semibold transition-colors",
                            active
                              ? "border-action bg-action text-white"
                              : "border-line-strong bg-white text-ink-soft hover:bg-surface-alt",
                          ].join(" ")}
                        >
                          {branch.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {visibleTanks.map((item) => (
                  <TankCard
                    key={item.id}
                    tank={item}
                    selected={item.id === tankId}
                    incomingL={litersNum}
                    onSelect={() => setTankId(item.id)}
                  />
                ))}
              </div>
              {visibleTanks.length === 0 ? (
                <p className="rounded-xl bg-surface-alt px-4 py-3 text-sm text-ink-soft">
                  {t.common.empty}
                </p>
              ) : null}
              {multiBranch && tank ? (
                <p className="text-sm text-ink-soft">
                  {t.branches.title}: <b className="text-ink">{tank.branch_name ?? "—"}</b>
                </p>
              ) : null}
            </div>
          </Card>

          {/* 2. Хэнээс, хэзээ, хэдээр */}
          <Card title={t.procurement.fuelReceipt}>
            <div className="grid gap-4 sm:grid-cols-2">
              <PickerField
                label={t.procurement.supplier}
                value={supplierId}
                options={supplierOptions}
                onChange={setSupplierId}
              />
              <DateField label={t.procurement.receiptDate} value={receiptDate} onChange={setReceiptDate} />
              <NumberField
                name="receipt-liters"
                label={t.procurement.liters}
                value={liters}
                onChange={setLiters}
                suffix={t.units.liter}
                maxDecimals={3}
              />
              <NumberField
                name="receipt-unit-cost"
                label={t.common.unitCost}
                value={unitCost}
                onChange={setUnitCost}
                suffix={t.units.perLiter}
              />
              <NumberField
                name="receipt-freight"
                label={t.procurement.freight}
                value={freight}
                onChange={setFreight}
                suffix={t.units.mnt}
              />
              <TextField label={t.procurement.invoiceNo} value={invoiceNo} onChange={setInvoiceNo} />
            </div>

            {/* Нэмэлт хэмжилтүүд — ихэнх таталтад хэрэггүй тул нууж эхэлнэ */}
            <div className="mt-4 border-t border-line pt-3">
              <button
                type="button"
                onClick={() => setShowExtra((v) => !v)}
                aria-expanded={showExtra}
                className="flex h-11 items-center rounded-lg px-3 text-[13px] font-medium text-ink-soft transition hover:bg-surface-sunken hover:text-ink"
              >
                {showExtra ? "−" : "+"} {t.procurement.density} / {t.procurement.temperature} /{" "}
                {t.common.note}
              </button>
              {showExtra ? (
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <NumberField
                    name="receipt-density"
                    label={t.procurement.density}
                    value={density}
                    onChange={setDensity}
                    maxDecimals={3}
                  />
                  <NumberField
                    name="receipt-temperature"
                    label={t.procurement.temperature}
                    value={temperature}
                    onChange={setTemperature}
                    suffix={t.units.celsius}
                    maxDecimals={1}
                  />
                  <div className="sm:col-span-2">
                    <TextAreaField label={t.common.note} value={note} onChange={setNote} />
                  </div>
                </div>
              ) : null}
            </div>
          </Card>
        </div>

        {/* Нийт дүн + хадгалах */}
        <div className="flex flex-col gap-4">
          <Card title={t.common.total} tone="dark">
            <dl className="flex flex-col gap-3">
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-ink-faint">{t.procurement.liters}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">{formatLiters(liters)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-ink-faint">{t.procurement.landedCost}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">
                  {formatMoneyExact(landedUnitCost)}
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3 border-t border-brand-700 pt-3">
                <dt className="text-sm text-ink-faint">{t.common.net}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">{formatMNT(subtotal)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-ink-faint">{t.common.vat}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">{formatMNT(vatAmount)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3 border-t border-brand-700 pt-3">
                <dt className="text-base font-semibold text-ink-invert">{t.common.gross}</dt>
                <dd className="num text-[40px] leading-none font-bold text-success">
                  {formatMNT(totalGross)}
                </dd>
              </div>
            </dl>
          </Card>

          {overCapacity ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              Савны багтаамжаас хэтэрч байна
            </p>
          ) : null}

          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}

          <Button
            variant="primary"
            size="lg"
            block
            icon={<Save />}
            disabled={!canSubmit}
            loading={createMutation.isPending}
            onClick={submit}
          >
            {t.common.save}
          </Button>
          <Button variant="secondary" size="md" block onClick={() => navigate("/receipts/fuel")}>
            {t.common.cancel}
          </Button>
          <p className="text-sm text-ink-soft">{t.procurement.postConfirm}</p>
        </div>
      </div>
    </div>
  );
}

export default FuelReceiptNewPage;
