import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Plus, Truck } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useFuelReceipts, usePostFuelReceiptMutation, useSuppliers } from "../../api/queries/procurement";
import type { FuelReceipt } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { DOC_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { daysAgoInput, formatDate, formatLiters, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, Pager, PickerField } from "../catalog/_shared";

type StatusFilter = "all" | "draft" | "posted";

const POST_HINT =
  "Батласнаар савны үлдэгдэл нэмэгдэж, нийлүүлэгчийн өглөг (данс 2101) үүсч, журналд бичигдэнэ. Буцаах боломжгүй.";

export function FuelReceiptsPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(29), to: todayInput() });
  const [status, setStatus] = useState<StatusFilter>("all");
  const [supplierId, setSupplierId] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [posting, setPosting] = useState<FuelReceipt | null>(null);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const receiptsQuery = useFuelReceipts({
    date_from: range.from,
    date_to: range.to,
    status: status === "all" ? undefined : status,
    supplier_id: supplierId || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const postMutation = usePostFuelReceiptMutation();

  const rows = useMemo(() => receiptsQuery.data?.items ?? [], [receiptsQuery.data]);
  const total = receiptsQuery.data?.total ?? 0;

  const pageTotals = useMemo(
    () => ({
      liters: dSum(rows.map((row) => row.liters)),
      gross: dSum(rows.map((row) => row.total_gross)),
      drafts: rows.filter((row) => row.status === "draft").length,
    }),
    [rows],
  );

  const supplierOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...(suppliersQuery.data?.items ?? []).map((supplier) => ({
        value: supplier.id,
        label: supplier.name,
        hint: supplier.register_no ?? undefined,
      })),
    ],
    [suppliersQuery.data],
  );

  const resetPage = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setOffset(0);
  };

  const confirmPost = (): void => {
    if (!posting) return;
    postMutation.mutate(posting.id, {
      onSuccess: () => {
        toastSuccess(t.procurement.posted);
        setPosting(null);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setPosting(null);
      },
    });
  };

  const columns: Column<FuelReceipt>[] = [
    {
      key: "number",
      header: "№",
      primary: true,
      numeric: true,
      width: "6rem",
      render: (row) => <span className="font-bold">{row.number}</span>,
    },
    {
      key: "receipt_date",
      header: t.procurement.receiptDate,
      numeric: true,
      render: (row) => formatDate(row.receipt_date),
    },
    { key: "supplier", header: t.procurement.supplier, render: (row) => row.supplier_name ?? "—" },
    {
      key: "tank",
      header: t.tanks.tank,
      hideOnMobile: true,
      render: (row) => (
        <span>
          {row.tank_name ?? "—"}
          {row.fuel_name ? <span className="text-ink-soft"> · {row.fuel_name}</span> : null}
        </span>
      ),
    },
    {
      key: "liters",
      header: t.procurement.liters,
      align: "right",
      numeric: true,
      render: (row) => formatLiters(row.liters),
    },
    {
      key: "landed",
      header: t.procurement.landedCost,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMoneyExact(row.landed_unit_cost),
    },
    {
      key: "total_gross",
      header: t.common.gross,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.total_gross)}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(DOC_STATUS_META, row.status, row.status_name)} />,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        row.status === "draft" ? (
          <Button variant="success" size="md" icon={<CheckCircle2 />} onClick={() => setPosting(row)}>
            {t.procurement.post}
          </Button>
        ) : (
          <span className="text-sm text-ink-soft">{formatDate(row.posted_at)}</span>
        ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.procurement.fuelReceipts}
        subtitle={t.procurement.fuelReceipt}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => navigate("/receipts/fuel/new")}>
            {t.procurement.newFuelReceipt}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.procurement.liters} value={formatLiters(pageTotals.liters, 0)} tone="action" />
        <StatBox label={t.common.gross} value={formatMNT(pageTotals.gross)} tone="success" />
        <StatBox
          label={t.procurement.draft}
          value={pageTotals.drafts}
          tone={pageTotals.drafts > 0 ? "warning" : "neutral"}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <DateRangePicker value={range} onChange={resetPage(setRange)} />
        <div className="flex flex-wrap items-end gap-3">
          <ChipGroup<StatusFilter>
            value={status}
            onChange={resetPage(setStatus)}
            options={[
              { value: "all", label: t.common.all },
              { value: "draft", label: t.procurement.draft },
              { value: "posted", label: t.procurement.posted },
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
          loading={receiptsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Truck className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => navigate("/receipts/fuel/new")}>
                  {t.procurement.newFuelReceipt}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      <ConfirmDialog
        open={posting !== null}
        title={t.procurement.post}
        variant="success"
        confirmLabel={t.procurement.post}
        loading={postMutation.isPending}
        onConfirm={confirmPost}
        onCancel={() => setPosting(null)}
        message={
          <div className="space-y-2">
            <p>{t.procurement.postConfirm}</p>
            <p className="text-ink-soft">{POST_HINT}</p>
            {posting ? (
              <p className="num font-bold text-ink">
                №{posting.number} · {formatLiters(posting.liters)} · {formatMNT(posting.total_gross)}
              </p>
            ) : null}
          </div>
        }
      />
    </div>
  );
}

export default FuelReceiptsPage;
