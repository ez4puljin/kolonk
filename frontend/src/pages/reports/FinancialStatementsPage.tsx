/**
 * Санхүүгийн тайлан (WP12) — шалгах баланс, орлого зардал, баланс,
 * мөнгөн урсгал, нөөцийн үнэлгээ ба бүрэн бүтэн байдлын шалгалт.
 *
 * Сервер: `/api/accounting/trial-balance`, `/api/accounting/statements/*`,
 * `/api/accounting/integrity` (queries/accounting.ts дахь hook-ууд).
 */

import { useMemo, useState } from "react";
import { Check, ShieldCheck, X } from "lucide-react";

import {
  useBalanceSheet,
  useCashFlow,
  useIncomeStatement,
  useIntegrityChecks,
  useInventoryValuation,
  useTrialBalance,
} from "../../api/queries/accounting";
import type {
  AccountingStatementRow,
  BalanceSheetRow,
  CashFlowRow,
  ProductValuationRow,
  TankValuationRow,
  TrialBalanceRow,
} from "../../api/types";
import { BarChart, type BarDatum } from "../../components/charts/BarChart";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, rangeFor, type DateRange } from "../../components/ui/DateRangePicker";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar, type TabItem } from "../../components/ui/TabBar";
import { t } from "../../i18n/mn";
import type { Tone } from "../../lib/constants";
import { dIsZero } from "../../lib/decimal";
import { formatDate, formatLiters, formatMNT, formatMoneyExact, formatNumber } from "../../lib/format";

type StatementTab = "trial" | "pnl" | "balance" | "cashflow" | "valuation";

const TABS: readonly TabItem<StatementTab>[] = [
  { value: "trial", label: t.accounting.trialBalance },
  { value: "pnl", label: t.accounting.incomeStatement },
  { value: "balance", label: t.accounting.balanceSheet },
  { value: "cashflow", label: t.accounting.cashFlow },
  { value: "valuation", label: t.accounting.inventoryValuation },
];

const ACCOUNT_TYPE_MN: Record<string, string> = {
  asset: t.accounting.accountTypes.asset,
  liability: t.accounting.accountTypes.liability,
  equity: t.accounting.accountTypes.equity,
  revenue: t.accounting.accountTypes.revenue,
  expense: t.accounting.accountTypes.expense,
};

const ACCOUNT_TYPE_TONE: Record<string, Tone> = {
  asset: "action",
  liability: "warning",
  equity: "brand",
  revenue: "success",
  expense: "danger",
};

const EVENT_TYPE_MN: Record<string, string> = {
  SALE_POSTED: t.sales.sale,
  VOUCHER_SOLD: t.partners.sellVoucher,
  PREPAID_TOPUP: t.partners.topup,
  FUEL_RECEIPT_POSTED: t.procurement.fuelReceipt,
  PURCHASE_POSTED: t.procurement.purchase,
  AP_PAYMENT: t.procurement.apPayment,
  AR_RECEIPT: t.partners.arPayment,
  SHIFT_CASH_SHORT: t.shift.short,
  SHIFT_CASH_OVER: t.shift.over,
  FUEL_VARIANCE_LOSS: t.tanks.varianceMovement,
  FUEL_VARIANCE_GAIN: t.tanks.varianceMovement,
  REFUND_POSTED: t.refunds.refund,
  CARD_SETTLEMENT: t.accounting.settlement,
  QR_SETTLEMENT: t.accounting.settlement,
  MANUAL_ENTRY: t.accounting.manualEntry,
};

function eventName(code: string): string {
  return EVENT_TYPE_MN[code] ?? code;
}

/** Тайлангийн хэсэг — мөрүүд ба нийлбэр. */
function StatementSection({
  title,
  rows,
  total,
  tone = "neutral",
}: {
  title: string;
  rows: readonly AccountingStatementRow[];
  total: string;
  tone?: Tone;
}) {
  const totalTone =
    tone === "success" ? "text-success-dark" : tone === "danger" ? "text-danger-dark" : "text-ink";

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between border-b border-line-strong pb-2">
        <h4 className="text-sm font-bold tracking-wide text-ink-soft uppercase">{title}</h4>
      </div>
      {rows.length === 0 ? (
        <p className="py-3 text-sm text-ink-faint">{t.common.none}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {rows.map((row) => (
            <li key={row.code} className="flex min-h-11 items-center justify-between gap-3 py-1.5">
              <span className="min-w-0 flex-1 truncate text-[15px] text-ink">
                <span className="num mr-2 text-ink-faint">{row.code}</span>
                {row.name_mn}
              </span>
              <span className="num shrink-0 font-semibold text-ink">{formatMNT(row.amount)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-1 flex min-h-12 items-center justify-between gap-3 border-t-2 border-line-strong pt-2">
        <span className="text-[15px] font-bold text-ink">{t.common.total}</span>
        <span className={`num text-xl font-bold ${totalTone}`}>{formatMNT(total)}</span>
      </div>
    </div>
  );
}

const trialColumns: Column<TrialBalanceRow>[] = [
  {
    key: "code",
    header: t.accounting.accountCode,
    primary: true,
    numeric: true,
    render: (row) => (
      <span className="num font-bold">
        {row.code} <span className="ml-2 font-semibold text-ink-soft">{row.name_mn}</span>
      </span>
    ),
  },
  {
    key: "type",
    header: t.accounting.accountType,
    hideOnMobile: true,
    render: (row) => (
      <StatusBadge
        size="sm"
        tone={ACCOUNT_TYPE_TONE[row.account_type] ?? "neutral"}
        label={ACCOUNT_TYPE_MN[row.account_type] ?? row.account_type}
      />
    ),
  },
  {
    key: "debit",
    header: t.accounting.debit,
    align: "right",
    numeric: true,
    render: (row) => formatMoneyExact(row.debit, false),
  },
  {
    key: "credit",
    header: t.accounting.credit,
    align: "right",
    numeric: true,
    render: (row) => formatMoneyExact(row.credit, false),
  },
  {
    key: "balance",
    header: t.common.balance,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.balance)}</span>,
  },
];

const cashFlowColumns: Column<CashFlowRow>[] = [
  {
    key: "event",
    header: t.accounting.eventType,
    primary: true,
    render: (row) => <span className="font-semibold">{eventName(row.event_type)}</span>,
  },
  {
    key: "inflow",
    header: t.accounting.inflow,
    align: "right",
    numeric: true,
    render: (row) => <span className="text-success-dark">{formatMNT(row.inflow)}</span>,
  },
  {
    key: "outflow",
    header: t.accounting.outflow,
    align: "right",
    numeric: true,
    render: (row) => <span className="text-danger-dark">{formatMNT(row.outflow)}</span>,
  },
  {
    key: "net",
    header: t.accounting.netChange,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.net)}</span>,
  },
];

const tankValuationColumns: Column<TankValuationRow>[] = [
  {
    key: "tank",
    header: t.tanks.tank,
    primary: true,
    render: (row) => (
      <span className="font-semibold">{`${row.tank_name} · ${row.fuel_name_mn ?? ""}`}</span>
    ),
  },
  {
    key: "qty",
    header: t.tanks.current,
    align: "right",
    numeric: true,
    render: (row) => formatLiters(row.qty),
  },
  {
    key: "cost",
    header: t.tanks.avgCost,
    align: "right",
    numeric: true,
    render: (row) => formatMoneyExact(row.avg_cost, false),
  },
  {
    key: "value",
    header: t.inventory.value,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.value)}</span>,
  },
];

const productValuationColumns: Column<ProductValuationRow>[] = [
  {
    key: "name",
    header: t.products.product,
    primary: true,
    render: (row) => (
      <span className="font-semibold">
        <span className="num mr-2 text-ink-faint">{row.sku}</span>
        {row.name_mn}
      </span>
    ),
  },
  {
    key: "qty",
    header: t.inventory.onHand,
    align: "right",
    numeric: true,
    render: (row) => formatNumber(row.qty, 0),
  },
  {
    key: "cost",
    header: t.tanks.avgCost,
    align: "right",
    numeric: true,
    render: (row) => formatMoneyExact(row.avg_cost, false),
  },
  {
    key: "value",
    header: t.inventory.value,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.value)}</span>,
  },
];

function BalanceColumn({ title, rows, total }: { title: string; rows: readonly BalanceSheetRow[]; total: string }) {
  return (
    <div className="flex flex-col">
      <h4 className="border-b border-line-strong pb-2 text-sm font-bold tracking-wide text-ink-soft uppercase">
        {title}
      </h4>
      {rows.length === 0 ? (
        <p className="py-3 text-sm text-ink-faint">{t.common.none}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {rows.map((row) => (
            <li key={row.code} className="flex min-h-11 items-center justify-between gap-3 py-1.5">
              <span className="min-w-0 flex-1 truncate text-[15px] text-ink">
                <span className="num mr-2 text-ink-faint">{row.code}</span>
                {row.name_mn}
              </span>
              <span className="num shrink-0 font-semibold text-ink">{formatMNT(row.balance)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-1 flex min-h-12 items-center justify-between gap-3 border-t-2 border-line-strong pt-2">
        <span className="text-[15px] font-bold text-ink">{t.common.total}</span>
        <span className="num text-xl font-bold text-ink">{formatMNT(total)}</span>
      </div>
    </div>
  );
}

export function FinancialStatementsPage() {
  const [tab, setTab] = useState<StatementTab>("trial");
  const [range, setRange] = useState<DateRange>(() => rangeFor("month"));

  const asOf = range.to;

  const trialQuery = useTrialBalance(asOf);
  const pnlQuery = useIncomeStatement(range.from, range.to, tab === "pnl");
  const balanceQuery = useBalanceSheet(asOf);
  const cashFlowQuery = useCashFlow(range.from, range.to, tab === "cashflow");
  const valuationQuery = useInventoryValuation();
  const integrityQuery = useIntegrityChecks();

  const marginBars: BarDatum[] = useMemo(
    () =>
      (pnlQuery.data?.fuel_margins ?? []).map((margin) => ({
        key: margin.fuel_id,
        label: margin.fuel_name_mn ?? margin.fuel_id.slice(0, 6),
        value: margin.margin,
        display: `${formatMNT(margin.margin)} · ${formatNumber(margin.margin_pct, 1)}${t.units.percent}`,
      })),
    [pnlQuery.data],
  );

  const trial = trialQuery.data;
  const balanced = trial ? dIsZero(trial.imbalance) : true;

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.reports.financial}
        subtitle={`${formatDate(range.from)} — ${formatDate(range.to)}`}
      >
        <div className="flex flex-col gap-3">
          <TabBar variant="underline" value={tab} onChange={setTab} items={TABS} />
          <DateRangePicker value={range} onChange={setRange} />
        </div>
      </PageHeader>

      {/* ---------------- Шалгах баланс ---------------- */}
      {tab === "trial" ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatBox label={t.accounting.totalDebit} value={formatMNT(trial?.total_debit ?? "0")} tone="action" />
            <StatBox label={t.accounting.totalCredit} value={formatMNT(trial?.total_credit ?? "0")} tone="action" />
            <StatBox
              label={t.accounting.imbalance}
              value={formatMoneyExact(trial?.imbalance ?? "0")}
              tone={balanced ? "success" : "danger"}
              hint={balanced ? t.accounting.balanced : t.accounting.notBalanced}
            />
          </div>

          {!balanced ? (
            <div className="flex items-center gap-3 rounded-xl border border-danger/40 bg-danger-soft px-4 py-3 text-danger-dark">
              <X className="h-6 w-6 shrink-0" />
              <span className="text-[15px] font-bold">{t.accounting.unbalanced}</span>
            </div>
          ) : null}

          <Card title={`${t.accounting.trialBalance} · ${t.accounting.asOf} ${formatDate(asOf)}`} flush>
            <DataTable
              columns={trialColumns}
              rows={trial?.accounts ?? []}
              rowKey={(row) => row.code}
              loading={trialQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
        </div>
      ) : null}

      {/* ---------------- Орлого зардлын тайлан ---------------- */}
      {tab === "pnl" ? (
        <div className="flex flex-col gap-4">
          {pnlQuery.isLoading ? (
            <div className="flex justify-center py-16 text-ink-soft">
              <Spinner size="lg" label={t.common.loading} />
            </div>
          ) : pnlQuery.data ? (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatBox label={t.accounting.revenue} value={formatMNT(pnlQuery.data.total_revenue)} tone="action" />
                <StatBox label={t.accounting.cogs} value={formatMNT(pnlQuery.data.total_cogs)} />
                <StatBox
                  label={t.accounting.grossProfit}
                  value={formatMNT(pnlQuery.data.gross_profit)}
                  tone="success"
                  size="lg"
                />
                <StatBox
                  label={t.accounting.netProfit}
                  value={formatMNT(pnlQuery.data.net_profit)}
                  tone={pnlQuery.data.net_profit.startsWith("-") ? "danger" : "success"}
                  size="lg"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Card title={t.accounting.revenue}>
                  <StatementSection
                    title={t.accounting.revenue}
                    rows={pnlQuery.data.revenue}
                    total={pnlQuery.data.total_revenue}
                    tone="success"
                  />
                </Card>
                <Card title={t.accounting.cogs}>
                  <StatementSection
                    title={t.accounting.cogs}
                    rows={pnlQuery.data.cogs}
                    total={pnlQuery.data.total_cogs}
                  />
                </Card>
                <Card title={t.accounting.expense}>
                  <StatementSection
                    title={t.accounting.expense}
                    rows={pnlQuery.data.expense}
                    total={pnlQuery.data.total_expense}
                    tone="danger"
                  />
                </Card>
              </div>

              <Card title={t.accounting.fuelMargins}>
                <BarChart data={marginBars} title={t.accounting.fuelMargins} orientation="horizontal" />
              </Card>
            </>
          ) : (
            <Card>
              <p className="py-6 text-center text-ink-soft">{t.reports.noData}</p>
            </Card>
          )}
        </div>
      ) : null}

      {/* ---------------- Баланс ---------------- */}
      {tab === "balance" ? (
        <div className="flex flex-col gap-4">
          {balanceQuery.isLoading ? (
            <div className="flex justify-center py-16 text-ink-soft">
              <Spinner size="lg" label={t.common.loading} />
            </div>
          ) : balanceQuery.data ? (
            <>
              <div
                className={[
                  "flex min-h-16 items-center gap-3 rounded-xl border px-4 py-3",
                  balanceQuery.data.is_balanced
                    ? "border-success/40 bg-success-soft text-success-dark"
                    : "border-danger/40 bg-danger-soft text-danger-dark",
                ].join(" ")}
              >
                {balanceQuery.data.is_balanced ? (
                  <Check className="h-6 w-6 shrink-0" />
                ) : (
                  <X className="h-6 w-6 shrink-0" />
                )}
                <span className="text-[15px] font-bold">
                  {balanceQuery.data.is_balanced ? t.accounting.balanced : t.accounting.notBalanced}
                </span>
                <span className="num ml-auto font-bold">
                  {`${t.accounting.difference}: ${formatMoneyExact(balanceQuery.data.difference)}`}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card title={t.accounting.assets} subtitle={`${t.accounting.asOf} ${formatDate(asOf)}`}>
                  <BalanceColumn
                    title={t.accounting.assets}
                    rows={balanceQuery.data.assets}
                    total={balanceQuery.data.total_assets}
                  />
                </Card>

                <Card title={`${t.accounting.liabilities} + ${t.accounting.equity}`}>
                  <div className="flex flex-col gap-5">
                    <BalanceColumn
                      title={t.accounting.liabilities}
                      rows={balanceQuery.data.liabilities}
                      total={balanceQuery.data.total_liabilities}
                    />
                    <BalanceColumn
                      title={t.accounting.equity}
                      rows={balanceQuery.data.equity}
                      total={balanceQuery.data.total_equity}
                    />
                    <div className="flex min-h-12 items-center justify-between gap-3 rounded-xl bg-surface-alt px-3 py-2">
                      <span className="text-[15px] font-semibold text-ink-soft">
                        {t.accounting.retainedEarnings}
                      </span>
                      <span className="num font-bold text-ink">
                        {formatMNT(balanceQuery.data.retained_earnings)}
                      </span>
                    </div>
                    <div className="flex min-h-14 items-center justify-between gap-3 border-t-2 border-line-strong pt-3">
                      <span className="text-base font-bold text-ink">{t.common.total}</span>
                      <span className="num text-2xl font-bold text-ink">
                        {formatMNT(balanceQuery.data.total_liabilities_equity)}
                      </span>
                    </div>
                  </div>
                </Card>
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {/* ---------------- Мөнгөн урсгал ---------------- */}
      {tab === "cashflow" ? (
        <div className="flex flex-col gap-4">
          {cashFlowQuery.data ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatBox
                label={t.accounting.openingBalance}
                value={formatMNT(cashFlowQuery.data.opening_balance)}
              />
              <StatBox
                label={t.accounting.inflow}
                value={formatMNT(cashFlowQuery.data.total_inflow)}
                tone="success"
              />
              <StatBox
                label={t.accounting.outflow}
                value={formatMNT(cashFlowQuery.data.total_outflow)}
                tone="danger"
              />
              <StatBox
                label={t.accounting.closingBalance}
                value={formatMNT(cashFlowQuery.data.closing_balance)}
                tone="action"
                size="lg"
                hint={`${t.accounting.netChange}: ${formatMNT(cashFlowQuery.data.net_change)}`}
              />
            </div>
          ) : null}

          <Card
            title={t.accounting.cashFlow}
            subtitle={(cashFlowQuery.data?.accounts ?? []).join(", ")}
            flush
          >
            <DataTable
              columns={cashFlowColumns}
              rows={cashFlowQuery.data?.flows ?? []}
              rowKey={(row) => row.event_type}
              loading={cashFlowQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
        </div>
      ) : null}

      {/* ---------------- Нөөцийн үнэлгээ ---------------- */}
      {tab === "valuation" ? (
        <div className="flex flex-col gap-4">
          {valuationQuery.data ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatBox label={t.inventory.fuelValue} value={formatMNT(valuationQuery.data.fuel_value)} />
              <StatBox label={t.inventory.goodsValue} value={formatMNT(valuationQuery.data.goods_value)} />
              <StatBox
                label={t.inventory.ledgerValue}
                value={formatMNT(valuationQuery.data.ledger_total)}
                tone="action"
              />
              <StatBox
                label={t.inventory.delta}
                value={formatMoneyExact(valuationQuery.data.total_delta)}
                tone={dIsZero(valuationQuery.data.total_delta) ? "success" : "danger"}
                hint={`${t.inventory.fuelValue}: ${formatMoneyExact(valuationQuery.data.fuel_delta)} · ${t.inventory.goodsValue}: ${formatMoneyExact(valuationQuery.data.goods_delta)}`}
              />
            </div>
          ) : null}

          <Card title={t.tanks.title} flush>
            <DataTable
              columns={tankValuationColumns}
              rows={valuationQuery.data?.tanks ?? []}
              rowKey={(row) => row.tank_id}
              loading={valuationQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>

          <Card title={t.products.title} flush>
            <DataTable
              columns={productValuationColumns}
              rows={valuationQuery.data?.products ?? []}
              rowKey={(row) => row.product_id}
              loading={valuationQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
        </div>
      ) : null}

      {/* ---------------- Бүрэн бүтэн байдал ---------------- */}
      <Card
        title={t.accounting.integrity}
        subtitle={
          integrityQuery.data && integrityQuery.data.every((check) => check.ok)
            ? t.accounting.integrityOk
            : t.accounting.integrityFail
        }
        actions={
          <StatusBadge
            tone={integrityQuery.data && integrityQuery.data.every((check) => check.ok) ? "success" : "danger"}
            label={
              integrityQuery.data && integrityQuery.data.every((check) => check.ok)
                ? t.accounting.integrityOk
                : t.accounting.integrityFail
            }
            icon={<ShieldCheck className="h-4 w-4" />}
          />
        }
      >
        {integrityQuery.isLoading ? (
          <div className="flex justify-center py-6 text-ink-soft">
            <Spinner label={t.common.loading} />
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {(integrityQuery.data ?? []).map((check) => (
              <li
                key={check.name}
                className={[
                  "flex min-h-14 flex-wrap items-center gap-3 rounded-xl border px-4 py-2.5",
                  check.ok ? "border-line bg-white" : "border-danger/40 bg-danger-soft",
                ].join(" ")}
              >
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                    check.ok ? "bg-success-soft text-success-dark" : "bg-danger text-white"
                  }`}
                >
                  {check.ok ? <Check className="h-5 w-5" /> : <X className="h-5 w-5" />}
                </span>
                <span className="min-w-0 flex-1 text-[15px] font-semibold text-ink">{check.name}</span>
                <span className="num flex shrink-0 flex-wrap items-center gap-x-4 gap-y-0.5 text-sm">
                  <span className="text-ink-soft">
                    {`${t.accounting.expected}: ${formatMoneyExact(check.expected, false)}`}
                  </span>
                  <span className="text-ink-soft">
                    {`${t.accounting.actual}: ${formatMoneyExact(check.actual, false)}`}
                  </span>
                  <span className={check.ok ? "font-bold text-success-dark" : "font-bold text-danger-dark"}>
                    {`${t.accounting.difference}: ${formatMoneyExact(check.difference, false)}`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default FinancialStatementsPage;
