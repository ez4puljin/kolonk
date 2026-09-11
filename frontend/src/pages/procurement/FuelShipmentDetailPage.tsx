import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Droplets, Lock, ShoppingCart, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBankAccounts } from "../../api/queries/bank";
import { useBranches } from "../../api/queries/branches";
import {
  useCloseShipmentMutation,
  useDeleteShipmentMutation,
  useFuelShipment,
  usePostShipmentMutation,
  useShipmentDeliverMutation,
  useShipmentOutflowMutation,
} from "../../api/queries/shipments";
import { useTanks } from "../../api/queries/tanks";
import type { FuelShipmentDetail, ShipmentItem } from "../../api/types";
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
import { formatDate, formatLiters, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, DateField, NumberField, PickerField, TextField } from "../catalog/_shared";

const POST_HINT =
  "Батласнаар нийлүүлэгчийн өглөг (нийт дүнгээр) нээгдэж, түлш «Замд яваа түлш» дансанд бүртгэгдэнэ. Дараа нь салбаруудад буулгаж эхэлнэ. Буцаах боломжгүй.";

/** Түгээлтийн цонх. */
function DeliverModal({
  shipment,
  onClose,
}: {
  shipment: FuelShipmentDetail;
  onClose: () => void;
}) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const tanksQuery = useTanks();
  const deliverMutation = useShipmentDeliverMutation();

  const [tankId, setTankId] = useState("");
  const [liters, setLiters] = useState("");
  const [when, setWhen] = useState(todayInput());

  const remainingByFuel = useMemo(() => {
    const map = new Map<string, ShipmentItem>();
    for (const item of shipment.items) map.set(item.fuel_id, item);
    return map;
  }, [shipment.items]);

  const tanks = useMemo(
    () =>
      (tanksQuery.data?.items ?? []).filter(
        (tank) => tank.is_active && remainingByFuel.has(tank.fuel_id),
      ),
    [tanksQuery.data, remainingByFuel],
  );

  const tankOptions = useMemo(
    () =>
      tanks.map((tank) => ({
        value: tank.id,
        label: `${tank.branch_name ? `${tank.branch_name} · ` : ""}${tank.name}`,
        hint: `${tank.fuel.name_mn} · ${formatLiters(tank.current_l, 0)}/${formatLiters(tank.capacity_l, 0)}`,
      })),
    [tanks],
  );

  const selectedTank = tanks.find((tank) => tank.id === tankId) ?? null;
  const fuelItem = selectedTank ? remainingByFuel.get(selectedTank.fuel_id) ?? null : null;
  const remaining = fuelItem ? Number(fuelItem.remaining_l) : 0;
  const litersNum = Number(liters) || 0;
  const freeCapacity = selectedTank
    ? Number(selectedTank.capacity_l) - Number(selectedTank.current_l)
    : 0;
  const overRemaining = litersNum > remaining;
  const overCapacity = selectedTank ? litersNum > freeCapacity + 0.001 : false;
  const canSubmit = Boolean(tankId) && litersNum > 0 && !overRemaining && !overCapacity;

  const submit = (): void => {
    if (!canSubmit) return;
    deliverMutation.mutate(
      { id: shipment.id, payload: { tank_id: tankId, liters, receipt_date: when || null } },
      {
        onSuccess: (row) => {
          toastSuccess(`${row.branch_name ?? row.tank_name ?? ""} — ${formatLiters(row.liters)} буулгалаа`);
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
      title="Саванд буулгах"
      subtitle={`Ачилт №${shipment.number} · ${shipment.vehicle_no}`}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="lg"
            icon={<Droplets />}
            disabled={!canSubmit}
            loading={deliverMutation.isPending}
            onClick={submit}
          >
            Буулгах
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label="Сав (салбар)" value={tankId} options={tankOptions} onChange={setTankId} />
        <NumberField
          name="deliver-liters"
          label="Литр"
          value={liters}
          onChange={setLiters}
          suffix="л"
          maxDecimals={3}
          hint={
            fuelItem
              ? `Машин дээр ${formatLiters(fuelItem.remaining_l)} ${fuelItem.fuel_name ?? ""} үлдсэн · Саванд ${formatLiters(String(freeCapacity))} багтана`
              : undefined
          }
        />
        {overRemaining ? (
          <p className="text-sm font-semibold text-danger-dark">Машин дээрх үлдэгдлээс их байна.</p>
        ) : null}
        {overCapacity ? (
          <p className="text-sm font-semibold text-danger-dark">Савны багтаамжаас хэтэрч байна.</p>
        ) : null}
        <DateField label="Огноо" value={when} onChange={setWhen} max={todayInput()} />
        {fuelItem ? (
          <p className="num text-sm text-ink-soft">
            Өртөг: {formatMoneyExact(fuelItem.landed_unit_cost)} ₮/л ·{" "}
            {litersNum > 0 ? `Дүн ${formatMNT(litersNum * Number(fuelItem.landed_unit_cost))}` : ""}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

/** Машинаас шууд борлуулах / хорогдол цонх. */
function OutflowModal({
  shipment,
  onClose,
}: {
  shipment: FuelShipmentDetail;
  onClose: () => void;
}) {
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
  const fuelOptions = withRemaining.map((item) => ({
    value: item.fuel_id,
    label: `${item.fuel_name ?? ""} — ${formatLiters(item.remaining_l)} үлдсэн`,
  }));
  const accountOptions = (bankAccountsQuery.data?.items ?? []).map((account) => ({
    value: account.id,
    label: `${account.bank_name} ${account.account_number}`,
  }));
  const branchOptions = [
    { value: "", label: "Толгой (хуваарилахгүй)" },
    ...(branchesQuery.data ?? []).map((branch) => ({ value: branch.id, label: branch.name })),
  ];

  const item = shipment.items.find((row) => row.fuel_id === fuelId) ?? null;
  const remaining = item ? Number(item.remaining_l) : 0;
  const litersNum = Number(liters) || 0;
  const priceNum = Number(unitPrice) || 0;
  const overRemaining = litersNum > remaining;
  const canSubmit =
    Boolean(fuelId) && litersNum > 0 && !overRemaining && (kind === "loss" || priceNum > 0);

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
          toastSuccess(kind === "sale" ? "Борлуулалт бүртгэгдлээ" : "Хорогдол бүртгэгдлээ");
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
      title="Машинаас шууд гаргах"
      subtitle="Саванд оруулалгүй зарах эсвэл хорогдолд бичих"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant={kind === "sale" ? "primary" : "warning"}
            size="lg"
            icon={kind === "sale" ? <ShoppingCart /> : <Trash2 />}
            disabled={!canSubmit}
            loading={outflowMutation.isPending}
            onClick={submit}
          >
            {kind === "sale" ? "Борлуулах" : "Хорогдолд бичих"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <ChipGroup<"sale" | "loss">
          value={kind}
          onChange={setKind}
          options={[
            { value: "sale", label: "Шууд борлуулалт" },
            { value: "loss", label: "Хорогдол / зарлага" },
          ]}
        />
        <PickerField label="Түлш" value={fuelId} options={fuelOptions} onChange={setFuelId} />
        <NumberField
          name="outflow-liters"
          label="Литр"
          value={liters}
          onChange={setLiters}
          suffix="л"
          maxDecimals={3}
          hint={item ? `Үлдсэн: ${formatLiters(item.remaining_l)}` : undefined}
        />
        {overRemaining ? (
          <p className="text-sm font-semibold text-danger-dark">Машин дээрх үлдэгдлээс их байна.</p>
        ) : null}
        {kind === "sale" ? (
          <>
            <NumberField
              name="outflow-price"
              label="Нэгж үнэ (НӨАТ-тай)"
              value={unitPrice}
              onChange={setUnitPrice}
              suffix="₮/л"
              maxDecimals={2}
            />
            {litersNum > 0 && priceNum > 0 ? (
              <p className="num font-bold text-ink">Нийт: {formatMNT(litersNum * priceNum)}</p>
            ) : null}
            <ChipGroup<"cash" | "bank">
              value={receivedTo}
              onChange={setReceivedTo}
              options={[
                { value: "bank", label: "Данс руу" },
                { value: "cash", label: "Бэлнээр" },
              ]}
            />
            {receivedTo === "bank" ? (
              <PickerField
                label="Хүлээн авах данс"
                value={bankAccountId}
                options={accountOptions}
                onChange={setBankAccountId}
              />
            ) : null}
            <TextField label="Худалдан авагч" value={customerName} onChange={setCustomerName} maxLength={128} />
            <PickerField
              label="Аль салбарын орлогод тооцох"
              value={branchId}
              options={branchOptions}
              onChange={setBranchId}
            />
          </>
        ) : null}
        <DateField label="Огноо" value={when} onChange={setWhen} max={todayInput()} />
      </div>
    </Modal>
  );
}

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
  const unpaid = Number(shipment.total_gross) - Number(shipment.amount_paid);

  const itemColumns: Column<ShipmentItem>[] = [
    {
      key: "fuel",
      header: "Түлш",
      primary: true,
      render: (row) => <span className="font-bold">{row.fuel_name ?? row.fuel_code ?? "—"}</span>,
    },
    { key: "liters", header: "Ачсан", align: "right", numeric: true, render: (row) => formatLiters(row.liters) },
    {
      key: "unit_cost",
      header: "Нэгж үнэ",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMoneyExact(row.unit_cost),
    },
    {
      key: "landed",
      header: "Тээвэртэй өртөг",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMoneyExact(row.landed_unit_cost),
    },
    { key: "amount", header: "Дүн", align: "right", numeric: true, render: (row) => formatMNT(row.amount) },
    {
      key: "delivered",
      header: "Буусан",
      align: "right",
      numeric: true,
      render: (row) => formatLiters(row.delivered_l),
    },
    {
      key: "outflow",
      header: "Зарсан/хорогдсон",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatLiters(row.outflow_l),
    },
    {
      key: "remaining",
      header: "Үлдсэн",
      align: "right",
      numeric: true,
      render: (row) => (
        <span className={Number(row.remaining_l) > 0 ? "font-bold text-warning-dark" : "text-ink-soft"}>
          {formatLiters(row.remaining_l)}
        </span>
      ),
    },
  ];

  const confirmAction = (): void => {
    if (confirming === "post") {
      postMutation.mutate(shipment.id, {
        onSuccess: () => {
          toastSuccess("Ачилт бүртгэгдлээ — түгээлт эхлүүлж болно");
          setConfirming(null);
        },
        onError: (error) => {
          toastError(errorMessage(error));
          setConfirming(null);
        },
      });
    } else if (confirming === "close") {
      closeMutation.mutate(shipment.id, {
        onSuccess: () => {
          toastSuccess("Ачилт хаагдлаа");
          setConfirming(null);
        },
        onError: (error) => {
          toastError(errorMessage(error));
          setConfirming(null);
        },
      });
    } else if (confirming === "delete") {
      deleteMutation.mutate(shipment.id, {
        onSuccess: () => {
          toastSuccess("Ачилт устлаа");
          navigate("/shipments", { replace: true });
        },
        onError: (error) => {
          toastError(errorMessage(error));
          setConfirming(null);
        },
      });
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={`Ачилт №${shipment.number}`}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>
              {shipment.vehicle_no}
              {shipment.driver_name ? ` · ${shipment.driver_name}` : ""} · {shipment.supplier_name}
            </span>
            <StatusBadge
              size="sm"
              meta={statusMeta(SHIPMENT_STATUS_META, shipment.status, shipment.status_name ?? undefined)}
            />
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="lg" icon={<ArrowLeft />} onClick={() => navigate("/shipments")}>
              {t.common.back}
            </Button>
            {isDraft ? (
              <>
                <Button variant="danger" size="lg" icon={<Trash2 />} onClick={() => setConfirming("delete")}>
                  {t.common.delete}
                </Button>
                <Button variant="success" size="lg" icon={<CheckCircle2 />} onClick={() => setConfirming("post")}>
                  Бүртгэх
                </Button>
              </>
            ) : null}
            {isPosted ? (
              <>
                <Button variant="primary" size="lg" icon={<Droplets />} onClick={() => setDelivering(true)}>
                  Саванд буулгах
                </Button>
                <Button variant="secondary" size="lg" icon={<ShoppingCart />} onClick={() => setOutflowing(true)}>
                  Шууд гаргах
                </Button>
                <Button
                  variant="warning"
                  size="lg"
                  icon={<Lock />}
                  disabled={remainingTotal > 0}
                  onClick={() => setConfirming("close")}
                >
                  Хаах
                </Button>
              </>
            ) : null}
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox label="Ачсан литр" value={formatLiters(shipment.total_liters, 0)} tone="action" />
        <StatBox
          label="Машин дээр үлдсэн"
          value={formatLiters(shipment.remaining_liters, 0)}
          tone={remainingTotal > 0 ? "warning" : "success"}
        />
        <StatBox label="Нийт дүн (НӨАТ-тай)" value={formatMNT(shipment.total_gross)} tone="neutral" />
        <StatBox
          label="Нийлүүлэгчид төлөх үлдэгдэл"
          value={formatMNT(String(unpaid))}
          tone={unpaid > 0 ? "danger" : "success"}
          hint={
            shipment.invoice_status ? (
              <StatusBadge size="sm" meta={statusMeta(INVOICE_STATUS_META, shipment.invoice_status)} />
            ) : undefined
          }
        />
      </div>

      {isPosted && unpaid > 0 ? (
        <Card tone="light" className="border-warning bg-warning-soft/30">
          <p className="text-sm">
            Нийлүүлэгчид төлөх <b className="num">{formatMNT(String(unpaid))}</b> үлдсэн байна. Төлбөрийг{" "}
            <button
              type="button"
              className="font-bold text-action underline"
              onClick={() => navigate("/accounting/apar")}
            >
              Өглөг, авлага
            </button>{" "}
            хэсгээс бүртгэлтэй данснаас төлнө.
          </p>
        </Card>
      ) : null}

      <Card title="Ачсан түлш" flush>
        <DataTable columns={itemColumns} rows={shipment.items} rowKey={(row) => row.id} />
      </Card>

      <Card title="Салбаруудад буулгасан" subtitle="Түгээлт бүр салбарын худалдан авалт болж, тооцоонд өр үүснэ" flush>
        <DataTable
          columns={[
            {
              key: "date",
              header: "Огноо",
              numeric: true,
              render: (row) => formatDate(row.receipt_date),
            },
            {
              key: "branch",
              header: "Салбар",
              primary: true,
              render: (row) => <span className="font-bold">{row.branch_name ?? "—"}</span>,
            },
            {
              key: "tank",
              header: t.tanks.tank,
              render: (row) => (
                <span>
                  {row.tank_name ?? "—"}
                  {row.fuel_name ? <span className="text-ink-soft"> · {row.fuel_name}</span> : null}
                </span>
              ),
            },
            {
              key: "liters",
              header: "Литр",
              align: "right",
              numeric: true,
              render: (row) => formatLiters(row.liters),
            },
            {
              key: "cost",
              header: "Нэгж өртөг",
              align: "right",
              numeric: true,
              hideOnMobile: true,
              render: (row) => formatMoneyExact(row.unit_cost),
            },
            {
              key: "subtotal",
              header: "Дүн",
              align: "right",
              numeric: true,
              render: (row) => <span className="font-bold">{formatMNT(row.subtotal)}</span>,
            },
          ]}
          rows={shipment.deliveries}
          rowKey={(row) => row.id}
          empty={
            <div className="px-4 py-10 text-center text-ink-soft">
              {isPosted ? "Буулгалт бүртгээгүй байна — «Саванд буулгах» товчоор эхэлнэ" : "Бүртгэсний дараа буулгаж эхэлнэ"}
            </div>
          }
        />
      </Card>

      {shipment.outflows.length > 0 || isPosted ? (
        <Card title="Машинаас шууд гаргасан" subtitle="Саванд оруулаагүй борлуулалт, хорогдол" flush>
          <DataTable
            columns={[
              {
                key: "date",
                header: "Огноо",
                numeric: true,
                render: (row) => formatDate(row.outflow_date),
              },
              { key: "kind", header: "Төрөл", render: (row) => row.kind_name ?? row.kind },
              { key: "fuel", header: "Түлш", render: (row) => row.fuel_name ?? "—" },
              {
                key: "liters",
                header: "Литр",
                align: "right",
                numeric: true,
                render: (row) => formatLiters(row.liters),
              },
              {
                key: "amount",
                header: "Дүн",
                align: "right",
                numeric: true,
                render: (row) =>
                  row.kind === "sale" ? <span className="font-bold">{formatMNT(row.amount)}</span> : <span className="text-ink-soft">—</span>,
              },
              {
                key: "who",
                header: "Худалдан авагч / салбар",
                hideOnMobile: true,
                render: (row) => row.customer_name ?? row.branch_name ?? "—",
              },
            ]}
            rows={shipment.outflows}
            rowKey={(row) => row.id}
            empty={<div className="px-4 py-8 text-center text-ink-soft">Бүртгэл алга</div>}
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
        title={confirming === "post" ? "Ачилт бүртгэх" : confirming === "close" ? "Ачилт хаах" : t.common.delete}
        variant={confirming === "delete" ? "danger" : "success"}
        confirmLabel={confirming === "post" ? "Бүртгэх" : confirming === "close" ? "Хаах" : t.common.delete}
        loading={postMutation.isPending || closeMutation.isPending || deleteMutation.isPending}
        onConfirm={confirmAction}
        onCancel={() => setConfirming(null)}
        message={
          <div className="space-y-2">
            {confirming === "post" ? <p>{POST_HINT}</p> : null}
            {confirming === "close" ? <p>Бүх литр тэглэгдсэн тул ачилтыг хаана. Дараа нь өөрчлөх боломжгүй.</p> : null}
            {confirming === "delete" ? <p>Ноорог ачилтыг бүрмөсөн устгана.</p> : null}
            <p className="num font-bold text-ink">
              №{shipment.number} · {shipment.vehicle_no} · {formatMNT(shipment.total_gross)}
            </p>
          </div>
        }
      />

      {delivering ? <DeliverModal shipment={shipment} onClose={() => setDelivering(false)} /> : null}
      {outflowing ? <OutflowModal shipment={shipment} onClose={() => setOutflowing(false)} /> : null}
    </div>
  );
}

export default FuelShipmentDetailPage;
