import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Truck } from "lucide-react";

import { useFuelShipments } from "../../api/queries/shipments";
import { useSuppliers } from "../../api/queries/procurement";
import type { FuelShipment } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { INVOICE_STATUS_META, PAGE_SIZE, SHIPMENT_STATUS_META, statusMeta } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { daysAgoInput, formatDate, formatLiters, formatMNT, todayInput } from "../../lib/format";
import { ChipGroup, Pager, PickerField } from "../catalog/_shared";

type StatusFilter = "all" | "draft" | "posted" | "closed";

export function FuelShipmentsPage() {
  const navigate = useNavigate();

  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(89), to: todayInput() });
  const [status, setStatus] = useState<StatusFilter>("all");
  const [supplierId, setSupplierId] = useState<string>("");
  const [offset, setOffset] = useState(0);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const shipmentsQuery = useFuelShipments({
    date_from: range.from,
    date_to: range.to,
    status: status === "all" ? undefined : status,
    supplier_id: supplierId || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const rows = useMemo(() => shipmentsQuery.data?.items ?? [], [shipmentsQuery.data]);
  const total = shipmentsQuery.data?.total ?? 0;

  const pageTotals = useMemo(
    () => ({
      liters: dSum(rows.map((row) => row.total_liters)),
      remaining: dSum(rows.map((row) => row.remaining_liters)),
      gross: dSum(rows.map((row) => row.total_gross)),
    }),
    [rows],
  );

  const supplierOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...(suppliersQuery.data?.items ?? []).map((supplier) => ({
        value: supplier.id,
        label: supplier.name,
      })),
    ],
    [suppliersQuery.data],
  );

  const resetPage = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setOffset(0);
  };

  const columns: Column<FuelShipment>[] = [
    {
      key: "number",
      header: "№",
      primary: true,
      numeric: true,
      width: "5rem",
      render: (row) => <span className="font-bold">{row.number}</span>,
    },
    {
      key: "shipment_date",
      header: "Огноо",
      numeric: true,
      render: (row) => formatDate(row.shipment_date),
    },
    {
      key: "vehicle",
      header: "Машин",
      render: (row) => (
        <span>
          <span className="font-bold">{row.vehicle_no}</span>
          {row.driver_name ? <span className="text-ink-soft"> · {row.driver_name}</span> : null}
        </span>
      ),
    },
    {
      key: "supplier",
      header: t.procurement.supplier,
      hideOnMobile: true,
      // Олон нийлүүлэгчтэй ачилт: бүх нийлүүлэгчийн нэр; бараатай бол тэмдэг.
      render: (row) => (
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span>
            {row.suppliers.length > 0
              ? row.suppliers.map((s) => s.supplier_name ?? "—").join(", ")
              : (row.supplier_name ?? "—")}
          </span>
          {Number(row.total_goods_qty) > 0 ? (
            <span className="rounded-md bg-violet-soft px-1.5 py-0.5 text-[11px] font-bold text-violet-dark">
              {t.shipments.goodsShort}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "liters",
      header: "Ачсан литр",
      align: "right",
      numeric: true,
      render: (row) => formatLiters(row.total_liters, 0),
    },
    {
      key: "remaining",
      header: "Үлдсэн",
      align: "right",
      numeric: true,
      render: (row) =>
        row.status === "posted" ? (
          <span className={Number(row.remaining_liters) > 0 ? "font-bold text-warning-dark" : "text-ink-soft"}>
            {formatLiters(row.remaining_liters, 0)}
          </span>
        ) : (
          <span className="text-ink-soft">—</span>
        ),
    },
    {
      key: "total_gross",
      header: t.common.gross,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.total_gross)}</span>,
    },
    {
      key: "payment",
      header: "Төлбөр",
      hideOnMobile: true,
      render: (row) =>
        row.invoice_status ? (
          <StatusBadge size="sm" meta={statusMeta(INVOICE_STATUS_META, row.invoice_status)} />
        ) : (
          <span className="text-sm text-ink-soft">—</span>
        ),
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => (
        <StatusBadge size="sm" meta={statusMeta(SHIPMENT_STATUS_META, row.status, row.status_name ?? undefined)} />
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.nav.shipments}
        subtitle="Машинаар татсан түлшийг салбаруудад түгээх"
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => navigate("/shipments/new")}>
            Шинэ ачилт
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label="Ачсан литр" value={formatLiters(pageTotals.liters, 0)} tone="action" />
        <StatBox
          label="Машин дээр үлдсэн"
          value={formatLiters(pageTotals.remaining, 0)}
          tone={Number(pageTotals.remaining) > 0 ? "warning" : "neutral"}
        />
        <StatBox label={t.common.gross} value={formatMNT(pageTotals.gross)} tone="success" />
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <DateRangePicker value={range} onChange={resetPage(setRange)} />
        <div className="flex flex-wrap items-end gap-3">
          <ChipGroup<StatusFilter>
            value={status}
            onChange={resetPage(setStatus)}
            options={[
              { value: "all", label: t.common.all },
              { value: "draft", label: t.status.draft },
              { value: "posted", label: "Түгээлтэд" },
              { value: "closed", label: "Хаагдсан" },
            ]}
          />
          <PickerField
            label={t.procurement.supplier}
            value={supplierId}
            options={supplierOptions}
            onChange={resetPage(setSupplierId)}
            className="min-w-[16rem]"
          />
        </div>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={(row) => navigate(`/shipments/${row.id}`)}
          loading={shipmentsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Truck className="h-7 w-7" />}
              title={t.common.empty}
              hint="Нийлүүлэгчээс машинаар түлш татахдаа энд ачилт бүртгэнэ"
              action={
                <Button variant="primary" size="md" onClick={() => navigate("/shipments/new")}>
                  Шинэ ачилт
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>
    </div>
  );
}

export default FuelShipmentsPage;
