import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Building2, CheckCircle2, Droplets, Lock, Package, Plus, ShoppingCart, Trash2, Truck } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBankAccounts } from "../../api/queries/bank";
import { useBranches } from "../../api/queries/branches";
import {
  useCloseShipmentMutation,
  useDeleteShipmentMutation,
  useFuelShipment,
  usePostShipmentMutation,
  useShipmentDeliverGoodsMutation,
  useShipmentDeliverManyMutation,
  useShipmentOutflowMutation,
} from "../../api/queries/shipments";
import { useTanks } from "../../api/queries/tanks";
import type { FuelShipmentDetail, ShipmentGoods, ShipmentItem, ShipmentSupplier } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { INVOICE_STATUS_META, SHIPMENT_STATUS_META, statusMeta } from "../../lib/constants";
import { formatDate, formatLiters, formatMNT, formatMoneyExact, formatNumber, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, DateField, NumberField, PickerField, TextField } from "../catalog/_shared";

const num = (value: string): number => Number(value) || 0;

// --------------------------------------------------------------------------
// Түлш буулгах — нэг зогсолтоор олон саванд
// --------------------------------------------------------------------------
interface DeliverRow {
  key: number;
  tank_id: string;
  liters: string;
}
let rowSeq = 0;

function DeliverModal({ shipment, onClose }: { shipment: FuelShipmentDetail; onClose: () => void }) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const tanksQuery = useTanks({ active_only: true });
  const deliverMutation = useShipmentDeliverManyMutation();

  const [rows, setRows] = useState<DeliverRow[]>([{ key: ++rowSeq, tank_id: "", liters: "" }]);
  const [when, setWhen] = useState(todayInput());

  const itemByFuel = useMemo(() => {
    const map = new Map<string, ShipmentItem>();
    for (const item of shipment.items) map.set(item.fuel_id, item);
    return map;
  }, [shipment.items]);

  const tanks = useMemo(
    () => (tanksQuery.data?.items ?? []).filter((tank) => itemByFuel.has(tank.fuel_id)),
    [tanksQuery.data, itemByFuel],
  );
  const tankOptions = useMemo(
    () =>
      tanks.map((tank) => ({
        value: tank.id,
        label: `${tank.branch_name ? `${tank.branch_name} · ` : ""}${tank.name}`,
        hint: `${tank.fuel.name_mn} · ${formatLiters(tank.current_l, 0)} / ${formatLiters(tank.capacity_l, 0)}`,
      })),
    [tanks],
  );

  const patch = (key: number, p: Partial<DeliverRow>): void =>
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...p } : r)));

  // Түлш бүрээр нийлбэр — машин дээрх үлдэгдэлтэй, сав бүрээр багтаамжтай тулгана.
  const check = useMemo(() => {
    const byFuel = new Map<string, number>();
    const problems: string[] = [];
    for (const r of rows) {
      const tank = tanks.find((x) => x.id === r.tank_id);
      if (!tank || num(r.liters) <= 0) continue;
      byFuel.set(tank.fuel_id, (byFuel.get(tank.fuel_id) ?? 0) + num(r.liters));
      const free = Number(tank.capacity_l) - Number(tank.current_l);
      if (Number(tank.capacity_l) > 0 && num(r.liters) > free + 0.001) problems.push(`${tank.name}: ${t.shipments.overCapacity}`);
    }
    for (const [fuelId, liters] of byFuel) {
      const item = itemByFuel.get(fuelId);
      if (item && liters > Number(item.remaining_l) + 0.0005) problems.push(`${item.fuel_name ?? ""}: ${t.shipments.overRemaining}`);
    }
    return problems;
  }, [rows, tanks, itemByFuel]);

  const valid = rows.filter((r) => r.tank_id && num(r.liters) > 0);
  const canSubmit = valid.length > 0 && check.length === 0;

  const submit = (): void => {
    if (!canSubmit) return;
    deliverMutation.mutate(
      {
        id: shipment.id,
        payload: { allocations: valid.map((r) => ({ tank_id: r.tank_id, liters: r.liters })), receipt_date: when || null },
      },
      {
        onSuccess: (result) => {
          toastSuccess(`${result.length} ${t.shipments.deliveredTanks}`);
          onClose();
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t.shipments.deliverTitle}
      subtitle={`${t.shipments.shipmentNo}${shipment.number} · ${shipment.vehicle_no}`}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>{t.common.cancel}</Button>
          <Button variant="primary" size="lg" icon={<Droplets />} disabled={!canSubmit} loading={deliverMutation.isPending} onClick={submit}>
            {t.shipments.deliver}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2 text-xs">
          {shipment.items.map((item) => (
            <span key={item.id} className={`num rounded-lg border px-2 py-1 font-semibold ${Number(item.remaining_l) > 0 ? "border-warning/40 bg-warning-soft text-warning-dark" : "border-line bg-surface-alt text-ink-soft"}`}>
              {item.fuel_name}: {formatLiters(item.remaining_l)} {t.shipments.onTruck}
            </span>
          ))}
        </div>
        {rows.map((r) => (
          <div key={r.key} className="grid items-end gap-2 sm:grid-cols-[1.5fr_0.8fr_auto]">
            <PickerField label={t.shipments.branchTank} value={r.tank_id} options={tankOptions} onChange={(v) => patch(r.key, { tank_id: v })} />
            <NumberField name={`dl-${r.key}`} label={t.common.liters} value={r.liters} onChange={(v) => patch(r.key, { liters: v })} suffix="л" maxDecimals={3} />
            <Button variant="ghost" size="md" icon={<Trash2 />} aria-label={t.common.delete} disabled={rows.length === 1} onClick={() => setRows((prev) => prev.filter((x) => x.key !== r.key))} />
          </div>
        ))}
        <Button variant="secondary" size="md" icon={<Plus />} className="self-start" onClick={() => setRows((prev) => [...prev, { key: ++rowSeq, tank_id: "", liters: "" }])}>
          {t.shipments.addTank}
        </Button>
        {check.map((p) => (
          <p key={p} className="text-sm font-semibold text-danger-dark">{p}</p>
        ))}
        <DateField label={t.common.date} value={when} onChange={setWhen} max={todayInput()} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Бараа буулгах — нэг салбарт, бараа бүрд тоо
// --------------------------------------------------------------------------
function DeliverGoodsModal({ shipment, onClose }: { shipment: FuelShipmentDetail; onClose: () => void }) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const branchesQuery = useBranches();
  const mutation = useShipmentDeliverGoodsMutation();

  const [branchId, setBranchId] = useState("");
  const [qty, setQty] = useState<Record<string, string>>({});
  const [when, setWhen] = useState(todayInput());

  const branchOptions = (branchesQuery.data ?? []).filter((b) => b.is_active).map((b) => ({ value: b.id, label: b.name, hint: b.code }));
  const withRemaining = shipment.goods.filter((g) => Number(g.remaining_qty) > 0);
  const lines = withRemaining.filter((g) => num(qty[g.product_id] ?? "") > 0);
  const over = withRemaining.some((g) => num(qty[g.product_id] ?? "") > Number(g.remaining_qty) + 0.0005);
  const canSubmit = Boolean(branchId) && lines.length > 0 && !over;

  const submit = (): void => {
    if (!canSubmit) return;
    mutation.mutate(
      {
        id: shipment.id,
        payload: { branch_id: branchId, lines: lines.map((g) => ({ product_id: g.product_id, qty: qty[g.product_id] })), receipt_date: when || null },
      },
      {
        onSuccess: (rows) => {
          toastSuccess(`${rows.length} ${t.shipments.deliveredGoods}`);
          onClose();
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t.shipments.deliverGoodsTitle}
      subtitle={`${t.shipments.shipmentNo}${shipment.number} · ${shipment.vehicle_no}`}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>{t.common.cancel}</Button>
          <Button variant="primary" size="lg" icon={<Package />} disabled={!canSubmit} loading={mutation.isPending} onClick={submit}>
            {t.shipments.deliver}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label={t.branches.title} value={branchId} options={branchOptions} onChange={setBranchId} />
        {withRemaining.length === 0 ? (
          <p className="text-sm text-ink-soft">{t.shipments.noGoodsLeft}</p>
        ) : (
          withRemaining.map((g) => (
            <NumberField
              key={g.id}
              name={`dg-${g.id}`}
              label={`${g.product_name ?? ""} — ${t.shipments.onTruck}: ${formatNumber(Number(g.remaining_qty), 3)} ${g.unit ?? ""}`}
              value={qty[g.product_id] ?? ""}
              onChange={(v) => setQty((prev) => ({ ...prev, [g.product_id]: v }))}
              suffix={g.unit ?? ""}
              maxDecimals={3}
            />
          ))
        )}
        {over ? <p className="text-sm font-semibold text-danger-dark">{t.shipments.overRemaining}</p> : null}
        <DateField label={t.common.date} value={when} onChange={setWhen} max={todayInput()} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Машинаас шууд борлуулах / хорогдол
// --------------------------------------------------------------------------
function OutflowModal({ shipment, onClose }: { shipment: FuelShipmentDetail; onClose: () => void }) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const outflowMutation = useShipmentOutflowMutation();
  const bankAccountsQuery = useBankAccounts({ active_only: true });
  const branchesQuery = useBranches();

  const [kind, setKind] = useState<"sale" | "loss">("sale");
  const [fuelId, setFuelId] = useState("");
  const [liters, setLiters] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [receivedTo, setReceivedTo] = useState<"cash" | "bank">("bank");
  const [bankAccountId, setBankAccountId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [when, setWhen] = useState(todayInput());

  const withRemaining = shipment.items.filter((item) => Number(item.remaining_l) > 0);
  const fuelOptions = withRemaining.map((item) => ({ value: item.fuel_id, label: `${item.fuel_name ?? ""} — ${formatLiters(item.remaining_l)}` }));
  const accountOptions = (bankAccountsQuery.data?.items ?? []).map((a) => ({ value: a.id, label: `${a.bank_name} ${a.account_number}` }));
  const branchOptions = [{ value: "", label: t.shipments.headOffice }, ...(branchesQuery.data ?? []).map((b) => ({ value: b.id, label: b.name }))];

  const item = shipment.items.find((row) => row.fuel_id === fuelId) ?? null;
  const litersNum = num(liters);
  const priceNum = num(unitPrice);
  const overRemaining = item ? litersNum > Number(item.remaining_l) : false;
  const canSubmit = Boolean(fuelId) && litersNum > 0 && !overRemaining && (kind === "loss" || priceNum > 0);

  const submit = (): void => {
    if (!canSubmit) return;
    outflowMutation.mutate(
      {
        id: shipment.id,
        payload: {
          kind,
          fuel_id: fuelId,
          liters,
          unit_price: kind === "sale" ? unitPrice : "0",
          received_to: receivedTo,
          bank_account_id: receivedTo === "bank" ? bankAccountId || null : null,
          branch_id: branchId || null,
          outflow_date: when || null,
          customer_name: customerName.trim() || null,
        },
      },
      {
        onSuccess: () => {
          toastSuccess(kind === "sale" ? t.shipments.saleRecorded : t.shipments.lossRecorded);
          onClose();
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t.shipments.outflowTitle}
      subtitle={t.shipments.outflowHint}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>{t.common.cancel}</Button>
          <Button variant={kind === "sale" ? "primary" : "warning"} size="lg" icon={kind === "sale" ? <ShoppingCart /> : <Trash2 />} disabled={!canSubmit} loading={outflowMutation.isPending} onClick={submit}>
            {kind === "sale" ? t.shipments.sell : t.shipments.writeOff}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <ChipGroup<"sale" | "loss"> value={kind} onChange={setKind} options={[{ value: "sale", label: t.shipments.directSale }, { value: "loss", label: t.shipments.loss }]} />
        <PickerField label={t.shipments.fuel} value={fuelId} options={fuelOptions} onChange={setFuelId} />
        <NumberField name="outflow-liters" label={t.common.liters} value={liters} onChange={setLiters} suffix="л" maxDecimals={3} hint={item ? `${t.shipments.onTruck}: ${formatLiters(item.remaining_l)}` : undefined} />
        {overRemaining ? <p className="text-sm font-semibold text-danger-dark">{t.shipments.overRemaining}</p> : null}
        {kind === "sale" ? (
          <>
            <NumberField name="outflow-price" label={t.shipments.unitPriceVat} value={unitPrice} onChange={setUnitPrice} suffix="₮/л" maxDecimals={2} />
            {litersNum > 0 && priceNum > 0 ? <p className="num font-bold text-ink">{t.common.total}: {formatMNT(litersNum * priceNum)}</p> : null}
            <ChipGroup<"cash" | "bank"> value={receivedTo} onChange={setReceivedTo} options={[{ value: "bank", label: t.shipments.toBank }, { value: "cash", label: t.shipments.toCash }]} />
            {receivedTo === "bank" ? <PickerField label={t.shipments.receivingAccount} value={bankAccountId} options={accountOptions} onChange={setBankAccountId} /> : null}
            <TextField label={t.shipments.buyer} value={customerName} onChange={setCustomerName} maxLength={128} />
            <PickerField label={t.shipments.revenueBranch} value={branchId} options={branchOptions} onChange={setBranchId} />
          </>
        ) : null}
        <DateField label={t.common.date} value={when} onChange={setWhen} max={todayInput()} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Дэлгэрэнгүй хуудас
// --------------------------------------------------------------------------
export function FuelShipmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const shipmentQuery = useFuelShipment(id);
  const postMutation = usePostShipmentMutation();
  const closeMutation = useCloseShipmentMutation();
  const deleteMutation = useDeleteShipmentMutation();

  const [confirming, setConfirming] = useState<"post" | "close" | "delete" | null>(null);
  const [delivering, setDelivering] = useState(false);
  const [deliveringGoods, setDeliveringGoods] = useState(false);
  const [outflowing, setOutflowing] = useState(false);

  const shipment = shipmentQuery.data ?? null;

  if (shipmentQuery.isLoading || !shipment) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  const isDraft = shipment.status === "draft";
  const isPosted = shipment.status === "posted";
  const remainingTotal = Number(shipment.remaining_liters);
  const remainingGoods = Number(shipment.remaining_goods_qty);
  const unpaid = Number(shipment.total_gross) - Number(shipment.amount_paid);
  const hasGoods = shipment.goods.length > 0;
  const planned = shipment.items.some((i) => i.allocations.length > 0) || shipment.goods.some((g) => g.allocations.length > 0);

  const itemColumns: Column<ShipmentItem>[] = [
    { key: "fuel", header: t.shipments.fuel, primary: true, render: (row) => <span className="font-bold">{row.fuel_name ?? row.fuel_code ?? "—"}</span> },
    { key: "supplier", header: t.procurement.supplier, hideOnMobile: true, render: (row) => row.supplier_name ?? "—" },
    { key: "liters", header: t.shipments.loaded, align: "right", numeric: true, render: (row) => formatLiters(row.liters) },
    { key: "unit_cost", header: t.shipments.unitCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.unit_cost) },
    { key: "landed", header: t.shipments.landedCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.landed_unit_cost) },
    { key: "amount", header: t.common.amount, align: "right", numeric: true, render: (row) => formatMNT(row.amount) },
    { key: "delivered", header: t.shipments.delivered, align: "right", numeric: true, render: (row) => formatLiters(row.delivered_l) },
    { key: "outflow", header: t.shipments.soldOrLost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatLiters(row.outflow_l) },
    {
      key: "remaining",
      header: t.shipments.remaining,
      align: "right",
      numeric: true,
      render: (row) => <span className={Number(row.remaining_l) > 0 ? "font-bold text-warning-dark" : "text-ink-soft"}>{formatLiters(row.remaining_l)}</span>,
    },
  ];

  const goodsColumns: Column<ShipmentGoods>[] = [
    { key: "product", header: t.shipments.product, primary: true, render: (row) => <span className="font-bold">{row.product_name ?? "—"}<span className="ml-1 text-xs text-ink-soft">{row.product_sku}</span></span> },
    { key: "supplier", header: t.procurement.supplier, hideOnMobile: true, render: (row) => row.supplier_name ?? "—" },
    { key: "qty", header: t.shipments.loaded, align: "right", numeric: true, render: (row) => `${formatNumber(Number(row.qty), 3)} ${row.unit ?? ""}` },
    { key: "unit_cost", header: t.shipments.unitCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.unit_cost) },
    { key: "landed", header: t.shipments.landedCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.landed_unit_cost) },
    { key: "amount", header: t.common.amount, align: "right", numeric: true, render: (row) => formatMNT(row.amount) },
    { key: "delivered", header: t.shipments.delivered, align: "right", numeric: true, render: (row) => formatNumber(Number(row.delivered_qty), 3) },
    {
      key: "remaining",
      header: t.shipments.remaining,
      align: "right",
      numeric: true,
      render: (row) => <span className={Number(row.remaining_qty) > 0 ? "font-bold text-warning-dark" : "text-ink-soft"}>{formatNumber(Number(row.remaining_qty), 3)}</span>,
    },
  ];

  const supplierColumns: Column<ShipmentSupplier>[] = [
    {
      key: "name",
      header: t.procurement.supplier,
      primary: true,
      render: (row) => (
        <span className="font-bold">
          {row.supplier_name ?? "—"}
          {row.is_main ? <span className="ml-2 rounded-md bg-warning-soft px-1.5 py-0.5 text-[11px] font-bold text-warning-dark">{t.shipments.mainSupplierTag}</span> : null}
        </span>
      ),
    },
    { key: "subtotal", header: t.shipments.subtotalNoVat, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMNT(row.subtotal) },
    { key: "vat", header: t.common.vat, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMNT(row.vat_amount) },
    { key: "gross", header: t.shipments.totalGross, align: "right", numeric: true, render: (row) => <span className="font-bold">{formatMNT(row.total_gross)}</span> },
    { key: "paid", header: t.shipments.paid, align: "right", numeric: true, render: (row) => formatMNT(row.amount_paid) },
    {
      key: "status",
      header: t.common.status,
      render: (row) => (row.invoice_status ? <StatusBadge size="sm" meta={statusMeta(INVOICE_STATUS_META, row.invoice_status)} /> : <span className="text-ink-soft">—</span>),
    },
  ];

  const confirmAction = (): void => {
    const done = (message: string) => () => {
      toastSuccess(message);
      setConfirming(null);
    };
    const fail = (error: unknown): void => {
      toastError(errorMessage(error));
      setConfirming(null);
    };
    if (confirming === "post") postMutation.mutate(shipment.id, { onSuccess: done(t.shipments.posted), onError: fail });
    else if (confirming === "close") closeMutation.mutate(shipment.id, { onSuccess: done(t.shipments.closed), onError: fail });
    else if (confirming === "delete")
      deleteMutation.mutate(shipment.id, {
        onSuccess: () => {
          toastSuccess(t.shipments.deleted);
          navigate("/shipments", { replace: true });
        },
        onError: fail,
      });
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={`${t.shipments.shipmentNo}${shipment.number}`}
        icon={<Truck className="h-6 w-6" />}
        iconTone="warning"
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>
              {shipment.vehicle_no}
              {shipment.driver_name ? ` · ${shipment.driver_name}` : ""} · {shipment.supplier_name}
              {shipment.supplier_count > 1 ? ` +${shipment.supplier_count - 1}` : ""}
            </span>
            <StatusBadge size="sm" meta={statusMeta(SHIPMENT_STATUS_META, shipment.status, shipment.status_name ?? undefined)} />
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="lg" icon={<ArrowLeft />} onClick={() => navigate("/shipments")}>{t.common.back}</Button>
            {isDraft ? (
              <>
                <Button variant="danger" size="lg" icon={<Trash2 />} onClick={() => setConfirming("delete")}>{t.common.delete}</Button>
                <Button variant="success" size="lg" icon={<CheckCircle2 />} onClick={() => setConfirming("post")}>{t.shipments.post}</Button>
              </>
            ) : null}
            {isPosted ? (
              <>
                <Button variant="primary" size="lg" icon={<Droplets />} disabled={remainingTotal <= 0} onClick={() => setDelivering(true)}>{t.shipments.deliverFuel}</Button>
                {hasGoods ? (
                  <Button variant="primary" size="lg" icon={<Package />} disabled={remainingGoods <= 0} onClick={() => setDeliveringGoods(true)}>{t.shipments.deliverGoods}</Button>
                ) : null}
                <Button variant="secondary" size="lg" icon={<ShoppingCart />} disabled={remainingTotal <= 0} onClick={() => setOutflowing(true)}>{t.shipments.outflow}</Button>
                <Button variant="warning" size="lg" icon={<Lock />} disabled={remainingTotal > 0 || remainingGoods > 0} onClick={() => setConfirming("close")}>{t.shipments.close}</Button>
              </>
            ) : null}
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox label={t.shipments.loadedLiters} value={formatLiters(shipment.total_liters, 0)} tone="action" hint={hasGoods ? `${t.shipments.goodsShort}: ${formatNumber(Number(shipment.total_goods_qty), 0)}` : undefined} />
        <StatBox
          label={t.shipments.onTruckStat}
          value={formatLiters(shipment.remaining_liters, 0)}
          tone={remainingTotal > 0 || remainingGoods > 0 ? "warning" : "success"}
          hint={hasGoods ? `${t.shipments.goodsShort}: ${formatNumber(remainingGoods, 0)}` : undefined}
        />
        <StatBox label={t.shipments.totalGross} value={formatMNT(shipment.total_gross)} tone="neutral" hint={`${shipment.supplier_count} ${t.shipments.suppliersShort}`} />
        <StatBox
          label={t.shipments.unpaid}
          value={formatMNT(String(unpaid))}
          tone={unpaid > 0 ? "danger" : "success"}
          hint={shipment.invoice_status ? <StatusBadge size="sm" meta={statusMeta(INVOICE_STATUS_META, shipment.invoice_status)} /> : undefined}
        />
      </div>

      {isPosted && unpaid > 0 ? (
        <Card tone="light" className="border-warning bg-warning-soft/30">
          <p className="text-sm">
            {t.shipments.unpaidHintBefore} <b className="num">{formatMNT(String(unpaid))}</b> {t.shipments.unpaidHintAfter}{" "}
            <button type="button" className="font-bold text-action underline" onClick={() => navigate("/accounting/apar")}>{t.nav.apar}</button>.
          </p>
        </Card>
      ) : null}

      <Card title={t.shipments.suppliersCard} subtitle={t.shipments.suppliersHint} flush>
        <DataTable columns={supplierColumns} rows={shipment.suppliers} rowKey={(row) => row.supplier_id} />
      </Card>

      <Card title={t.shipments.fuelCard} flush>
        <DataTable columns={itemColumns} rows={shipment.items} rowKey={(row) => row.id} empty={<div className="px-4 py-8 text-center text-ink-soft">{t.shipments.noFuelRows}</div>} />
      </Card>

      {hasGoods ? (
        <Card title={t.shipments.goodsCard} flush>
          <DataTable columns={goodsColumns} rows={shipment.goods} rowKey={(row) => row.id} />
        </Card>
      ) : null}

      {isDraft && planned ? (
        <Card title={t.shipments.planCard} subtitle={t.shipments.planCardHint}>
          <div className="grid gap-3 md:grid-cols-2">
            {shipment.items
              .filter((i) => i.allocations.length > 0)
              .map((i) => (
                <div key={i.id} className="rounded-xl border border-line p-3">
                  <div className="mb-1 flex items-center gap-1.5 font-bold text-ink"><Droplets className="h-4 w-4 text-action" />{i.fuel_name}</div>
                  <ul className="space-y-0.5 text-sm">
                    {i.allocations.map((a, idx) => (
                      <li key={idx} className="flex justify-between"><span>{a.branch_name ? `${a.branch_name} · ` : ""}{a.tank_name}</span><span className="num font-semibold">{formatLiters(a.liters)}</span></li>
                    ))}
                  </ul>
                </div>
              ))}
            {shipment.goods
              .filter((g) => g.allocations.length > 0)
              .map((g) => (
                <div key={g.id} className="rounded-xl border border-line p-3">
                  <div className="mb-1 flex items-center gap-1.5 font-bold text-ink"><Building2 className="h-4 w-4 text-violet" />{g.product_name}</div>
                  <ul className="space-y-0.5 text-sm">
                    {g.allocations.map((a, idx) => (
                      <li key={idx} className="flex justify-between"><span>{a.branch_name}</span><span className="num font-semibold">{formatNumber(Number(a.qty), 3)} {g.unit ?? ""}</span></li>
                    ))}
                  </ul>
                </div>
              ))}
          </div>
        </Card>
      ) : null}

      <Card title={t.shipments.deliveriesCard} subtitle={t.shipments.deliveriesHint} flush>
        <DataTable
          columns={[
            { key: "date", header: t.common.date, numeric: true, render: (row) => formatDate(row.receipt_date) },
            { key: "branch", header: t.branches.title, primary: true, render: (row) => <span className="font-bold">{row.branch_name ?? "—"}</span> },
            { key: "tank", header: t.tanks.tank, render: (row) => <span>{row.tank_name ?? "—"}{row.fuel_name ? <span className="text-ink-soft"> · {row.fuel_name}</span> : null}</span> },
            { key: "liters", header: t.common.liters, align: "right", numeric: true, render: (row) => formatLiters(row.liters) },
            { key: "cost", header: t.shipments.unitCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.unit_cost) },
            { key: "subtotal", header: t.common.amount, align: "right", numeric: true, render: (row) => <span className="font-bold">{formatMNT(row.subtotal)}</span> },
          ]}
          rows={shipment.deliveries}
          rowKey={(row) => row.id}
          empty={<div className="px-4 py-10 text-center text-ink-soft">{isPosted ? t.shipments.noDeliveriesPosted : t.shipments.noDeliveriesDraft}</div>}
        />
      </Card>

      {hasGoods ? (
        <Card title={t.shipments.goodsDeliveriesCard} subtitle={t.shipments.goodsDeliveriesHint} flush>
          <DataTable
            columns={[
              { key: "date", header: t.common.date, numeric: true, render: (row) => formatDate(row.receipt_date) },
              { key: "branch", header: t.branches.title, primary: true, render: (row) => <span className="font-bold">{row.branch_name ?? "—"}</span> },
              { key: "product", header: t.shipments.product, render: (row) => row.product_name ?? "—" },
              { key: "qty", header: t.common.qty, align: "right", numeric: true, render: (row) => `${formatNumber(Number(row.qty), 3)} ${row.unit ?? ""}` },
              { key: "cost", header: t.shipments.unitCost, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMoneyExact(row.unit_cost) },
              { key: "amount", header: t.common.amount, align: "right", numeric: true, render: (row) => <span className="font-bold">{formatMNT(row.amount)}</span> },
            ]}
            rows={shipment.goods_deliveries}
            rowKey={(row) => row.id}
            empty={<div className="px-4 py-8 text-center text-ink-soft">{isPosted ? t.shipments.noGoodsDeliveriesPosted : t.shipments.noDeliveriesDraft}</div>}
          />
        </Card>
      ) : null}

      {shipment.outflows.length > 0 || isPosted ? (
        <Card title={t.shipments.outflowCard} subtitle={t.shipments.outflowCardHint} flush>
          <DataTable
            columns={[
              { key: "date", header: t.common.date, numeric: true, render: (row) => formatDate(row.outflow_date) },
              { key: "kind", header: t.common.type, render: (row) => row.kind_name ?? row.kind },
              { key: "fuel", header: t.shipments.fuel, render: (row) => row.fuel_name ?? "—" },
              { key: "liters", header: t.common.liters, align: "right", numeric: true, render: (row) => formatLiters(row.liters) },
              { key: "amount", header: t.common.amount, align: "right", numeric: true, render: (row) => (row.kind === "sale" ? <span className="font-bold">{formatMNT(row.amount)}</span> : <span className="text-ink-soft">—</span>) },
              { key: "who", header: t.shipments.buyerOrBranch, hideOnMobile: true, render: (row) => row.customer_name ?? row.branch_name ?? "—" },
            ]}
            rows={shipment.outflows}
            rowKey={(row) => row.id}
            empty={<div className="px-4 py-8 text-center text-ink-soft">{t.common.empty}</div>}
          />
        </Card>
      ) : null}

      {shipment.note ? (
        <Card title={t.common.note}>
          <p className="whitespace-pre-wrap text-ink">{shipment.note}</p>
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirming !== null}
        title={confirming === "post" ? t.shipments.postTitle : confirming === "close" ? t.shipments.closeTitle : t.common.delete}
        variant={confirming === "delete" ? "danger" : "success"}
        confirmLabel={confirming === "post" ? t.shipments.post : confirming === "close" ? t.shipments.close : t.common.delete}
        loading={postMutation.isPending || closeMutation.isPending || deleteMutation.isPending}
        onConfirm={confirmAction}
        onCancel={() => setConfirming(null)}
        message={
          <div className="space-y-2">
            {confirming === "post" ? <p>{t.shipments.postHint}{planned ? ` ${t.shipments.postPlanHint}` : ""}</p> : null}
            {confirming === "close" ? <p>{t.shipments.closeHint}</p> : null}
            {confirming === "delete" ? <p>{t.shipments.deleteHint}</p> : null}
            <p className="num font-bold text-ink">
              №{shipment.number} · {shipment.vehicle_no} · {formatMNT(shipment.total_gross)} · {shipment.supplier_count} {t.shipments.suppliersShort}
            </p>
          </div>
        }
      />

      {delivering ? <DeliverModal shipment={shipment} onClose={() => setDelivering(false)} /> : null}
      {deliveringGoods ? <DeliverGoodsModal shipment={shipment} onClose={() => setDeliveringGoods(false)} /> : null}
      {outflowing ? <OutflowModal shipment={shipment} onClose={() => setOutflowing(false)} /> : null}
    </div>
  );
}

export default FuelShipmentDetailPage;
