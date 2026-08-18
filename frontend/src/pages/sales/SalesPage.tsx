import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Receipt } from "lucide-react";

import { useSales } from "../../api/queries/sales";
import { useUsers } from "../../api/queries/users";
import type { PaymentMethod, SaleRow } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { PAGE_SIZE, SALE_STATUS_META, statusMeta, TENDER_METHODS } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { formatDateTime, formatMNT, todayInput } from "../../lib/format";
import { Pager, PickerField } from "../catalog/_shared";

type MethodFilter = "all" | PaymentMethod;

const SALE_TYPE_LABEL: Record<string, string> = {
  fuel: t.sales.fuel,
  store: t.sales.store,
  mixed: t.sales.mixed,
};

export function SalesPage() {
  const navigate = useNavigate();

  const [range, setRange] = useState<DateRange>({ from: todayInput(), to: todayInput() });
  const [method, setMethod] = useState<MethodFilter>("all");
  const [cashierId, setCashierId] = useState("");
  const [offset, setOffset] = useState(0);

  const usersQuery = useUsers({ limit: 200 });
  const salesQuery = useSales({
    date_from: range.from,
    date_to: range.to,
    method: method === "all" ? undefined : method,
    limit: PAGE_SIZE,
    offset,
  });

  const serverRows = useMemo(() => salesQuery.data?.items ?? [], [salesQuery.data]);
  const total = salesQuery.data?.total ?? 0;

  // Сервер `cashier_id` шүүлтийг эрхээс хамааруулж өөрөө тодорхойлдог тул
  // түгээгчийн шүүлтийг харагдаж буй хуудсан дээр клиент талд хийнэ.
  const rows = useMemo(
    () => (cashierId === "" ? serverRows : serverRows.filter((row) => row.cashier_id === cashierId)),
    [serverRows, cashierId],
  );

  const pageTotals = useMemo(
    () => ({
      count: rows.length,
      gross: dSum(rows.map((row) => row.total)),
      vat: dSum(rows.map((row) => row.vat_amount)),
    }),
    [rows],
  );

  const cashierOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...(usersQuery.data?.items ?? []).map((user) => ({
        value: user.id,
        label: user.full_name,
        hint: user.role_name_mn,
      })),
    ],
    [usersQuery.data],
  );

  const methodOptions = useMemo(
    () => [
      { value: "all", label: t.common.all },
      ...TENDER_METHODS.map((tender) => ({ value: tender.value, label: tender.label })),
    ],
    [],
  );

  const columns: Column<SaleRow>[] = [
    {
      key: "number",
      header: t.sales.saleNo,
      primary: true,
      numeric: true,
      width: "7rem",
      render: (row) => <span className="font-bold">№{row.number}</span>,
    },
    {
      key: "completed_at",
      header: t.common.dateTime,
      numeric: true,
      render: (row) => formatDateTime(row.completed_at ?? row.created_at),
    },
    { key: "cashier", header: t.sales.cashier, render: (row) => row.cashier_name ?? "—" },
    {
      key: "sale_type",
      header: t.sales.saleType,
      hideOnMobile: true,
      render: (row) => SALE_TYPE_LABEL[row.sale_type] ?? row.sale_type,
    },
    {
      key: "items_count",
      header: t.sales.items,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => row.items_count,
    },
    {
      key: "methods",
      header: t.tender.title,
      render: (row) => (
        <span className="flex flex-wrap gap-1.5">
          {(row.method_names.length > 0 ? row.method_names : row.methods).map((name, index) => (
            <StatusBadge key={`${row.id}-${index}`} size="sm" tone="neutral" label={name} />
          ))}
        </span>
      ),
    },
    {
      key: "customer",
      header: t.partners.customer,
      hideOnMobile: true,
      render: (row) => row.customer_name ?? "—",
    },
    {
      key: "total",
      header: t.common.total,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-lg font-bold">{formatMNT(row.total)}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(SALE_STATUS_META, row.status, row.status_name)} />,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.sales.title}
        icon={<Receipt className="h-6 w-6" />}
        iconTone="action" subtitle={t.shift.salesSummary} />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.reports.transactions} value={pageTotals.count} tone="neutral" />
        <StatBox label={t.common.total} value={formatMNT(pageTotals.gross)} tone="success" size="lg" />
        <StatBox label={t.common.vat} value={formatMNT(pageTotals.vat)} tone="action" />
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <DateRangePicker
          value={range}
          onChange={(next) => {
            setRange(next);
            setOffset(0);
          }}
        />
        <div className="flex flex-wrap items-end gap-3">
          <PickerField
            label={t.tender.title}
            value={method}
            options={methodOptions}
            searchable={false}
            onChange={(next) => {
              setMethod(next as MethodFilter);
              setOffset(0);
            }}
            className="min-w-[13rem]"
          />
          <PickerField
            label={t.sales.filterByCashier}
            value={cashierId}
            options={cashierOptions}
            onChange={setCashierId}
            className="min-w-[15rem]"
          />
        </div>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={(row) => navigate(`/sales/${row.id}`)}
          loading={salesQuery.isLoading}
          empty={
            <EmptyState icon={<Receipt className="h-7 w-7" />} title={t.sales.noSales} hint={t.common.emptyHint} />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>
    </div>
  );
}

export default SalesPage;
