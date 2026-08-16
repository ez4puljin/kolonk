import { useNavigate, useParams } from "react-router-dom";
import { BookOpen, Printer, RotateCcw } from "lucide-react";

import { useSale, useSaleReceipt } from "../../api/queries/sales";
import type { Payment, ReceiptPayload, SaleItem } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { usePermission } from "../../hooks/usePermission";
import { usePrint } from "../../hooks/usePrint";
import { t } from "../../i18n/mn";
import { EBARIMT_STATUS_META, SALE_STATUS_META, statusMeta, tenderLabel } from "../../lib/constants";
import { dCmp } from "../../lib/decimal";
import { formatDateTime, formatMNT, formatMoneyExact, formatQty } from "../../lib/format";
import { KeyValue } from "../catalog/_shared";

/** 80мм баримтын хэвлэх хэлбэр. */
function ReceiptSheet({ receipt }: { receipt: ReceiptPayload }) {
  return (
    <div className="print-sheet" style={{ width: "72mm", fontSize: "11px", color: "#000" }}>
      <div style={{ textAlign: "center", marginBottom: "6px" }}>
        <div style={{ fontWeight: 700, fontSize: "14px" }}>{receipt.station.name}</div>
        <div>{receipt.station.address}</div>
        <div>{receipt.station.phone}</div>
        <div>
          {t.admin.vatPayerNo}: {receipt.station.vat_payer_no}
        </div>
      </div>
      <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
      <div>
        {t.sales.saleNo} {receipt.number}
      </div>
      <div>{formatDateTime(receipt.sold_at)}</div>
      <div>
        {t.sales.cashier}: {receipt.cashier_name ?? "—"}
      </div>
      {receipt.customer_name ? (
        <div>
          {t.partners.customer}: {receipt.customer_name}
        </div>
      ) : null}
      <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
      {receipt.items.map((item) => (
        <div key={item.line_no} style={{ marginBottom: "3px" }}>
          <div>{item.name}</div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>
              {formatQty(item.qty, item.unit)} × {formatMoneyExact(item.unit_price, false)}
            </span>
            <span>{formatMoneyExact(item.amount, false)}</span>
          </div>
        </div>
      ))}
      <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>{t.common.net}</span>
        <span>{formatMoneyExact(receipt.subtotal, false)}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>{t.common.vat}</span>
        <span>{formatMoneyExact(receipt.vat_amount, false)}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, fontSize: "14px" }}>
        <span>{t.common.total}</span>
        <span>{formatMoneyExact(receipt.total, false)}</span>
      </div>
      <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
      {receipt.payments.map((payment, index) => (
        <div key={`${payment.method}-${index}`} style={{ display: "flex", justifyContent: "space-between" }}>
          <span>{payment.method_name}</span>
          <span>{formatMoneyExact(payment.amount, false)}</span>
        </div>
      ))}
      {dCmp(receipt.change_total, "0") > 0 ? (
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span>{t.tender.change}</span>
          <span>{formatMoneyExact(receipt.change_total, false)}</span>
        </div>
      ) : null}
      {receipt.ebarimt?.lottery_no ? (
        <>
          <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
          <div>
            {t.sales.lotteryNo}: {receipt.ebarimt.lottery_no}
          </div>
          <div>
            {t.sales.ebarimtId}: {receipt.ebarimt.receipt_id ?? "—"}
          </div>
        </>
      ) : null}
      <div style={{ borderTop: "1px dashed #000", margin: "4px 0" }} />
      <div style={{ textAlign: "center" }}>{receipt.station.footer}</div>
    </div>
  );
}

export function SaleDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { canAny } = usePermission();
  const { print, portal } = usePrint();

  const saleQuery = useSale(id);
  const receiptQuery = useSaleReceipt(id);

  const sale = saleQuery.data ?? null;
  const canRefund = canAny(["sales.refund.request", "sales.refund.approve"]);

  const itemColumns: Column<SaleItem>[] = [
    {
      key: "name",
      header: t.sales.items,
      primary: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="font-semibold text-ink">{row.name_snapshot}</span>
          <span className="text-xs text-ink-soft">
            {row.item_type === "fuel" ? t.sales.fuel : t.sales.store}
          </span>
        </span>
      ),
    },
    { key: "qty", header: t.common.qty, align: "right", numeric: true, render: (row) => formatQty(row.qty) },
    {
      key: "unit_price",
      header: t.common.unitPrice,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.unit_price),
    },
    {
      key: "amount",
      header: t.common.amount,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.amount)}</span>,
    },
    {
      key: "cogs",
      header: t.shift.cogs,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.cogs_amount),
    },
    {
      key: "refunded_qty",
      header: t.refunds.refundQty,
      align: "right",
      numeric: true,
      render: (row) =>
        dCmp(row.refunded_qty, "0") > 0 ? (
          <span className="font-semibold text-danger-dark">{formatQty(row.refunded_qty)}</span>
        ) : (
          "—"
        ),
    },
  ];

  const paymentColumns: Column<Payment>[] = [
    {
      key: "method",
      header: t.tender.title,
      primary: true,
      render: (row) => (
        <StatusBadge size="sm" tone="action" label={row.method_name || tenderLabel(row.method)} />
      ),
    },
    {
      key: "amount",
      header: t.common.amount,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.amount)}</span>,
    },
    {
      key: "received",
      header: t.tender.received,
      align: "right",
      numeric: true,
      render: (row) => (row.received ? formatMNT(row.received) : "—"),
    },
    {
      key: "change_given",
      header: t.tender.change,
      align: "right",
      numeric: true,
      render: (row) => (row.change_given ? formatMNT(row.change_given) : "—"),
    },
    {
      key: "ref_no",
      header: t.tender.refNo,
      numeric: true,
      hideOnMobile: true,
      render: (row) => row.ref_no ?? "—",
    },
  ];

  if (saleQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (!sale) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.sales.sale} back="/sales" />
        <EmptyState title={t.errors.notFound} hint={t.errors.notFoundHint} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={`${t.sales.saleNo} ${sale.number}`}
        subtitle={formatDateTime(sale.completed_at ?? sale.created_at)}
        back="/sales"
        actions={
          <>
            <Button
              variant="secondary"
              size="md"
              icon={<Printer />}
              disabled={!receiptQuery.data}
              onClick={() => receiptQuery.data && print(<ReceiptSheet receipt={receiptQuery.data} />)}
            >
              {t.sales.reprint}
            </Button>
            <Button
              variant="ghost"
              size="md"
              icon={<BookOpen />}
              onClick={() => navigate("/accounting/journal")}
            >
              {t.accounting.generalJournal}
            </Button>
            {canRefund && sale.status !== "refunded" ? (
              <Button
                variant="danger"
                size="lg"
                icon={<RotateCcw />}
                onClick={() => navigate(`/sales/${sale.id}/refund`)}
              >
                {t.refunds.newRefund}
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox label={t.common.total} value={formatMNT(sale.total)} tone="success" size="lg" />
        <StatBox label={t.common.vat} value={formatMNT(sale.vat_amount)} tone="neutral" />
        <StatBox label={t.shift.cogs} value={formatMNT(sale.cogs_total)} tone="warning" />
        <StatBox
          label={t.common.status}
          value={<StatusBadge meta={statusMeta(SALE_STATUS_META, sale.status, sale.status_name)} />}
          tone="neutral"
        />
      </div>

      <Card title={t.common.details}>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KeyValue label={t.sales.cashier} value={sale.cashier_name ?? "—"} />
          <KeyValue label={t.shift.number} value={sale.shift_number ?? "—"} numeric />
          <KeyValue label={t.partners.customer} value={sale.customer_name ?? "—"} />
          <KeyValue label={t.partners.contractNo} value={sale.contract_no ?? "—"} numeric />
        </div>
        {sale.note ? <p className="mt-4 text-sm text-ink-soft">{sale.note}</p> : null}
      </Card>

      <Card title={t.sales.items} flush>
        <DataTable
          columns={itemColumns}
          rows={sale.items}
          rowKey={(row) => row.id}
          empty={<EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />}
        />
      </Card>

      <Card title={t.sales.payments} flush>
        <DataTable
          columns={paymentColumns}
          rows={sale.payments}
          rowKey={(row) => row.id}
          empty={<EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />}
        />
      </Card>

      {sale.ebarimt ? (
        <Card title={t.sales.ebarimt}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KeyValue
              label={t.common.status}
              value={
                <StatusBadge
                  size="sm"
                  meta={statusMeta(EBARIMT_STATUS_META, sale.ebarimt.status, sale.ebarimt.status_name)}
                />
              }
            />
            <KeyValue label={t.sales.ebarimtId} value={sale.ebarimt.receipt_id ?? "—"} numeric />
            <KeyValue label={t.sales.lotteryNo} value={sale.ebarimt.lottery_no ?? "—"} numeric />
            <KeyValue label={t.common.dateTime} value={formatDateTime(sale.ebarimt.sent_at)} numeric />
          </div>
        </Card>
      ) : null}

      {portal}
    </div>
  );
}

export default SaleDetailPage;
