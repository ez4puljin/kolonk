import { useMemo, useState } from "react";
import { Building2, Scale } from "lucide-react";

import { useIncomeStatement } from "../../api/queries/accounting";
import { useBranchSummary } from "../../api/queries/shipments";
import type { AccountingStatementRow, BranchSummaryRow } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { daysAgoInput, formatMNT, todayInput } from "../../lib/format";
import { PickerField } from "../catalog/_shared";

/** Дүнг өнгөөр: ашиг ногоон, алдагдал улаан. */
function SignedMoney({ value, bold = false }: { value: string; bold?: boolean }) {
  const n = Number(value);
  const tone = n > 0 ? "text-success-dark" : n < 0 ? "text-danger-dark" : "text-ink-soft";
  return <span className={`num ${bold ? "font-bold" : ""} ${tone}`}>{formatMNT(value)}</span>;
}

/** Нэг талын (орлого/зардлын) дансны задаргаа. */
function StatementSection({ title, rows, total }: { title: string; rows: AccountingStatementRow[]; total: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between border-b border-line pb-1.5">
        <span className="text-sm font-bold tracking-wide text-ink-soft uppercase">{title}</span>
        <span className="num font-bold text-ink">{formatMNT(total)}</span>
      </div>
      {rows.length === 0 ? (
        <p className="py-2 text-sm text-ink-soft">Бичилт алга</p>
      ) : (
        rows.map((row) => (
          <div key={row.code} className="flex items-baseline justify-between py-0.5 text-sm">
            <span className="text-ink">
              <span className="num text-ink-faint">{row.code}</span> {row.name_mn}
            </span>
            <span className="num">{formatMNT(row.amount)}</span>
          </div>
        ))
      )}
    </div>
  );
}

export function BranchReportPage() {
  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(29), to: todayInput() });
  const [branchId, setBranchId] = useState("");

  const summaryQuery = useBranchSummary(range.from, range.to);
  const summary = summaryQuery.data ?? null;

  const pnlQuery = useIncomeStatement(range.from, range.to, Boolean(branchId), branchId);
  const pnl = pnlQuery.data ?? null;

  const rows = useMemo(() => summary?.items ?? [], [summary]);

  const branchOptions = useMemo(
    () => [
      { value: "", label: "— Салбар сонгох —" },
      ...rows
        .filter((row) => row.branch_id !== null)
        .map((row) => ({ value: row.branch_id as string, label: row.branch_name })),
    ],
    [rows],
  );

  const selectedName =
    rows.find((row) => row.branch_id === branchId)?.branch_name ?? "";

  const columns: Column<BranchSummaryRow>[] = [
    {
      key: "branch",
      header: t.nav.branches,
      primary: true,
      render: (row) => (
        <span className="font-bold">
          {row.branch_name}
          {row.branch_code ? <span className="text-ink-soft"> ({row.branch_code})</span> : null}
        </span>
      ),
    },
    {
      key: "revenue",
      header: "Орлого",
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.revenue),
    },
    {
      key: "cogs",
      header: "Өртөг",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.cogs),
    },
    {
      key: "gross",
      header: "Нийт ашиг",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => <SignedMoney value={row.gross_profit} />,
    },
    {
      key: "expense",
      header: "Зардал",
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.expense),
    },
    {
      key: "net",
      header: "Цэвэр ашиг",
      align: "right",
      numeric: true,
      render: (row) => <SignedMoney value={row.net_profit} bold />,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.nav.branchReport}
        subtitle="Салбар бүрийн орлого, зардал, ашгийн харьцуулалт"
      />

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {summary ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatBox label="Нийт орлого" value={formatMNT(summary.total_revenue)} tone="action" />
          <StatBox label="Нийт өртөг" value={formatMNT(summary.total_cogs)} tone="neutral" />
          <StatBox label="Үйл ажиллагааны зардал" value={formatMNT(summary.total_expense)} tone="warning" />
          <StatBox
            label="Цэвэр ашиг"
            value={formatMNT(summary.total_net_profit)}
            tone={Number(summary.total_net_profit) >= 0 ? "success" : "danger"}
          />
        </div>
      ) : null}

      <Card title="Салбаруудын харьцуулалт" flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.branch_id ?? "unallocated"}
          onRowClick={(row) => {
            if (row.branch_id) setBranchId(row.branch_id);
          }}
          loading={summaryQuery.isLoading}
          empty={
            <EmptyState
              icon={<Scale className="h-7 w-7" />}
              title={t.common.empty}
              hint="Гүйлгээ бүртгэгдмэгц салбар бүрийн дүн энд гарна"
            />
          }
        />
      </Card>

      <Card
        title="Салбарын дэлгэрэнгүй тайлан"
        subtitle="Сонгосон салбарын орлого, зардлын задаргаа"
        actions={
          <PickerField label="" value={branchId} options={branchOptions} onChange={setBranchId} className="min-w-[16rem]" />
        }
      >
        {!branchId ? (
          <EmptyState
            icon={<Building2 className="h-7 w-7" />}
            title="Салбар сонгоно уу"
            hint="Дээрх хүснэгтийн мөр дээр дарж эсвэл сонголтоос салбараа сонгоно"
          />
        ) : pnl ? (
          <div className="flex flex-col gap-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatBox label={`${selectedName} — орлого`} value={formatMNT(pnl.total_revenue)} tone="action" />
              <StatBox label="Нийт ашиг" value={formatMNT(pnl.gross_profit)} tone="neutral" />
              <StatBox
                label="Цэвэр ашиг"
                value={formatMNT(pnl.net_profit)}
                tone={Number(pnl.net_profit) >= 0 ? "success" : "danger"}
              />
            </div>
            <div className="grid gap-6 lg:grid-cols-3">
              <StatementSection title="Орлого" rows={pnl.revenue} total={pnl.total_revenue} />
              <StatementSection title="Борлуулалтын өртөг" rows={pnl.cogs} total={pnl.total_cogs} />
              <StatementSection title="Үйл ажиллагааны зардал" rows={pnl.expense} total={pnl.total_expense} />
            </div>
            {pnl.fuel_margins.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-sm font-bold tracking-wide text-ink-soft uppercase">Түлш бүрийн ашиг</span>
                {pnl.fuel_margins.map((margin) => (
                  <div key={margin.fuel_id} className="flex items-baseline justify-between py-0.5 text-sm">
                    <span>{margin.fuel_name_mn ?? "—"}</span>
                    <span className="num">
                      {formatMNT(margin.revenue)} − {formatMNT(margin.cogs)} ={" "}
                      <SignedMoney value={margin.margin} bold />
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="py-6 text-center text-ink-soft">{t.common.loading}</p>
        )}
      </Card>
    </div>
  );
}

export default BranchReportPage;
