/**
 * Өдрийн тооцоо — түгээгч бүрийн хаагдсан өдрийн ээлжийн жагсаалт.
 *
 * Мөр бүр: миль×үнэ түлшний орлого, зээл, тос/бараа, settlement,
 * кассын зөрүү. Мөр дээр дарвал ээлжийн бүрэн тайлан руу орно.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarCheck, Fuel } from "lucide-react";

import { useDailyClosings } from "../../api/queries/shifts";
import type { DailyClosingRow } from "../../api/types";
import { Card } from "../../components/ui/Card";
import { Column, DataTable } from "../../components/ui/DataTable";
import { DateRangePicker } from "../../components/ui/DateRangePicker";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { formatMNT } from "../../lib/format";

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function monthStartIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`;
}

export function DailyClosingsPage() {
  const navigate = useNavigate();
  const [dateFrom, setDateFrom] = useState(monthStartIso);
  const [dateTo, setDateTo] = useState(todayIso);

  const listQuery = useDailyClosings({ date_from: dateFrom, date_to: dateTo });
  const rows = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  const fuelSum = useMemo(
    () => rows.reduce((sum, row) => sum + Number(row.fuel_total), 0),
    [rows],
  );

  const columns: Column<DailyClosingRow>[] = [
    {
      key: "date",
      header: t.dailyClosings.date,
      render: (row) => <span className="num">{row.date}</span>,
      width: "7rem",
    },
    {
      key: "number",
      header: t.dailyClosings.shiftNo,
      render: (row) => <span className="num">№{row.shift_number}</span>,
      width: "5rem",
      hideOnMobile: true,
    },
    {
      key: "attendant",
      header: t.dailyClosings.attendant,
      render: (row) => row.attendant || "—",
      primary: true,
    },
    {
      key: "opening",
      header: t.dailyClosings.openingCash,
      render: (row) => formatMNT(row.opening_cash),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "fuel",
      header: t.dailyClosings.fuelTotal,
      render: (row) => <span className="font-bold">{formatMNT(row.fuel_total)}</span>,
      align: "right",
      numeric: true,
    },
    {
      key: "credit",
      header: t.dailyClosings.creditTotal,
      render: (row) => formatMNT(row.credit_total),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "oil",
      header: t.dailyClosings.oilTotal,
      render: (row) => formatMNT(row.oil_total),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "settlement",
      header: t.dailyClosings.settlementTotal,
      render: (row) => formatMNT(row.settlement_total),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "declared",
      header: t.dailyClosings.declaredCash,
      render: (row) => (row.declared_cash === null ? "—" : formatMNT(row.declared_cash)),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "over_short",
      header: t.dailyClosings.overShort,
      render: (row) => {
        if (row.cash_over_short === null) return "—";
        const value = Number(row.cash_over_short);
        const tone =
          value < 0 ? "text-danger-dark" : value > 0 ? "text-warning-dark" : "text-success-dark";
        return <span className={`font-bold ${tone}`}>{formatMNT(row.cash_over_short)}</span>;
      },
      align: "right",
      numeric: true,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t.dailyClosings.title}</h1>
          <p className="text-sm text-ink-soft">{t.dailyClosings.subtitle}</p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatBox
          label={t.dailyClosings.periodFuel}
          value={formatMNT(fuelSum.toFixed(2))}
          icon={<Fuel />}
          tone="action"
          size="lg"
        />
        <StatBox
          label={t.dailyClosings.periodCount}
          value={rows.length}
          icon={<CalendarCheck />}
        />
        <Card className="p-4">
          <DateRangePicker
            value={{ from: dateFrom, to: dateTo }}
            onChange={(range) => {
              setDateFrom(range.from);
              setDateTo(range.to);
            }}
          />
        </Card>
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.shift_id}
        loading={listQuery.isLoading}
        emptyTitle={t.dailyClosings.empty}
        onRowClick={(row) => navigate(`/shift/report/${row.shift_id}`)}
      />
    </div>
  );
}

export default DailyClosingsPage;
