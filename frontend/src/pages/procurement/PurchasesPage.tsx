import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Plus, ShoppingCart } from "lucide-react";

import { errorMessage } from "../../api/client";
import { usePostPurchaseMutation, usePurchases, useSuppliers } from "../../api/queries/procurement";
import type { Purchase } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { DOC_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { daysAgoInput, formatDate, formatMNT, formatQty, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, KeyValue, Pager, PickerField } from "../catalog/_shared";

type StatusFilter = "all" | "draft" | "posted";

const POST_HINT =
  "Батласнаар бараа хөдлөх дундаж өртгөөр нөөцөд орж, нийлүүлэгчийн өглөг (данс 2101) үүсч, журналд бичигдэнэ. Буцаах боломжгүй.";

export function PurchasesPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(29), to: todayInput() });
  const [status, setStatus] = useState<StatusFilter>("all");
  const [supplierId, setSupplierId] = useState("");
  const [offset, setOffset] = useState(0);
  const [posting, setPosting] = useState<Purchase | null>(null);
  const [detail, setDetail] = useState<Purchase | null>(null);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const purchasesQuery = usePurchases({
    date_from: range.from,
    date_to: range.to,
    status: status === "all" ? undefined : status,
    supplier_id: supplierId || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const postMutation = usePostPurchaseMutation();

  const rows = useMemo(() => purchasesQuery.data?.items ?? [], [purchasesQuery.data]);
  const total = purchasesQuery.data?.total ?? 0;

  const pageTotals = useMemo(
    () => ({
      gross: dSum(rows.map((row) => row.total_gross)),
      vat: dSum(rows.map((row) => row.vat_amount)),
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
      })),
    ],
    [suppliersQuery.data],
  );

  const confirmPost = (): void => {
    if (!posting) return;
    postMutation.mutate(posting.id, {
      onSuccess: () => {
        toastSuccess(t.procurement.posted);
        setPosting(null);
        setDetail(null);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setPosting(null);
      },
    });
  };

  const columns: Column<Purchase>[] = [
    {
      key: "number",
      header: "№",
      primary: true,
      numeric: true,
      width: "6rem",
      render: (row) => <span className="font-bold">{row.number}</span>,
    },
    {
      key: "purchase_date",
      header: t.procurement.purchaseDate,
      numeric: true,
      render: (row) => formatDate(row.purchase_date),
    },
    { key: "supplier", header: t.procurement.supplier, render: (row) => row.supplier_name ?? "—" },
    {
      key: "invoice_no",
      header: t.procurement.invoiceNo,
      hideOnMobile: true,
      render: (row) => row.invoice_no ?? "—",
    },
    {
      key: "items",
      header: t.sales.items,
      align: "right",
      numeric: true,
      render: (row) => row.items.length,
    },
    {
      key: "subtotal",
      header: t.common.net,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.subtotal),
    },
    {
      key: "vat",
      header: t.common.vat,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.vat_amount),
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
      // Мобайл картад мөр өөрөө товч болдог тул давхар товч зурахгүй.
      hideOnMobile: true,
      render: (row) =>
        row.status === "draft" ? (
          <Button
            variant="success"
            size="md"
            icon={<CheckCircle2 />}
            onClick={(event) => {
              event.stopPropagation();
              setPosting(row);
            }}
          >
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
        title={t.procurement.purchases}
        subtitle={t.procurement.purchase}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => navigate("/purchases/new")}>
            {t.procurement.newPurchase}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.common.gross} value={formatMNT(pageTotals.gross)} tone="success" />
        <StatBox label={t.common.vat} value={formatMNT(pageTotals.vat)} tone="neutral" />
        <StatBox
          label={t.procurement.draft}
          value={pageTotals.drafts}
          tone={pageTotals.drafts > 0 ? "warning" : "neutral"}
        />
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
          <ChipGroup<StatusFilter>
            value={status}
            onChange={(next) => {
              setStatus(next);
              setOffset(0);
            }}
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
            onChange={(next) => {
              setSupplierId(next);
              setOffset(0);
            }}
            className="min-w-[16rem]"
          />
        </div>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={setDetail}
          loading={purchasesQuery.isLoading}
          empty={
            <EmptyState
              icon={<ShoppingCart className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => navigate("/purchases/new")}>
                  {t.procurement.newPurchase}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        size="lg"
        title={detail ? `${t.procurement.purchase} №${detail.number}` : ""}
        subtitle={detail?.supplier_name ?? undefined}
      >
        {detail ? (
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue label={t.procurement.purchaseDate} value={formatDate(detail.purchase_date)} numeric />
              <KeyValue label={t.procurement.invoiceNo} value={detail.invoice_no ?? "—"} />
              <KeyValue
                label={t.common.status}
                value={<StatusBadge size="sm" meta={statusMeta(DOC_STATUS_META, detail.status, detail.status_name)} />}
              />
              <KeyValue label={t.common.gross} value={formatMNT(detail.total_gross)} numeric />
            </div>

            <div className="overflow-hidden rounded-xl border border-line">
              <table className="w-full border-collapse text-[15px]">
                <thead>
                  <tr className="border-b border-line-strong bg-surface-alt">
                    <th className="px-3 py-2.5 text-left text-xs font-bold text-ink-soft uppercase">
                      {t.products.product}
                    </th>
                    <th className="px-3 py-2.5 text-right text-xs font-bold text-ink-soft uppercase">
                      {t.common.qty}
                    </th>
                    <th className="px-3 py-2.5 text-right text-xs font-bold text-ink-soft uppercase">
                      {t.common.unitCost}
                    </th>
                    <th className="px-3 py-2.5 text-right text-xs font-bold text-ink-soft uppercase">
                      {t.common.amount}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((item) => (
                    <tr key={item.id} className="border-b border-line last:border-b-0">
                      <td className="px-3 py-2.5">
                        <span className="font-semibold text-ink">{item.product_name ?? "—"}</span>
                        {item.sku ? <span className="ml-2 text-sm text-ink-soft">{item.sku}</span> : null}
                      </td>
                      <td className="num px-3 py-2.5 text-right">{formatQty(item.qty)}</td>
                      <td className="num px-3 py-2.5 text-right">{formatMNT(item.unit_cost)}</td>
                      <td className="num px-3 py-2.5 text-right font-bold">{formatMNT(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {detail.note ? <p className="text-sm text-ink-soft">{detail.note}</p> : null}

            {detail.status === "draft" ? (
              <Button
                variant="success"
                size="lg"
                block
                icon={<CheckCircle2 />}
                onClick={() => setPosting(detail)}
              >
                {t.procurement.post}
              </Button>
            ) : null}
          </div>
        ) : null}
      </Modal>

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
                №{posting.number} · {formatMNT(posting.total_gross)}
              </p>
            ) : null}
          </div>
        }
      />
    </div>
  );
}

export default PurchasesPage;
