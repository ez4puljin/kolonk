import type { ShiftReport } from "../../api/types";
import { t } from "../../i18n/mn";
import { dIsNegative, dIsZero } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMoneyExact, formatPct } from "../../lib/format";

import "./print.css";

export interface ShiftReportTemplateProps {
  report: ShiftReport;
  /** Толгойд гарах станцын нэр (тохиргооноос). */
  stationName?: string;
}

/** А4 хуудсанд шилжүүлэх — баримтын 80мм `@page`-ыг дарж бичнэ. */
const PAGE_OVERRIDE = "@media print{@page{size:A4 portrait;margin:12mm}}";

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className="sr-kv">
      <span>{label}</span>
      <span className="sr-num">{value}</span>
    </div>
  );
}

function overShortLabel(value: string | null): string {
  if (value === null || dIsZero(value)) return t.shift.overShort;
  return dIsNegative(value) ? t.shift.short : t.shift.over;
}

/** Ээлжийн хаалтын тайлангийн хэвлэх хувилбар. */
export function ShiftReportTemplate({ report, stationName }: ShiftReportTemplateProps) {
  const { shift, sales, cash, profit, tanks, nozzles, fuels, refunds } = report;

  return (
    <div className="sr-sheet print-sheet">
      <style>{PAGE_OVERRIDE}</style>

      <div className="sr-title">
        {stationName ? `${stationName} — ` : ""}
        {t.shift.reportOf}
        {shift.number}
      </div>
      <div className="sr-sub">
        {t.shift.opened}: {formatDateTime(shift.opened_at)} · {shift.opened_by_name ?? ""}
        {shift.closed_at ? (
          <>
            {" · "}
            {t.shift.closed}: {formatDateTime(shift.closed_at)} · {shift.closed_by_name ?? ""}
          </>
        ) : null}
      </div>

      {/* --- Борлуулалт --- */}
      <div className="sr-section">{t.shift.salesSummary}</div>
      <div className="sr-grid">
        <Kv label={t.reports.transactions} value={String(sales.count)} />
        <Kv label={t.common.gross} value={formatMoneyExact(sales.gross_total)} />
        <Kv label={t.common.vat} value={formatMoneyExact(sales.vat_total)} />
        <Kv label={t.common.net} value={formatMoneyExact(sales.net_total)} />
        <Kv label={t.sales.fuel} value={formatMoneyExact(sales.fuel_amount)} />
        <Kv label={t.reports.litersSold} value={formatLiters(sales.fuel_liters, 3)} />
        <Kv label={t.sales.store} value={formatMoneyExact(sales.store_amount)} />
      </div>

      {/* --- Төлбөрийн хэрэгслээр --- */}
      <div className="sr-section">{t.shift.byTender}</div>
      <table className="sr-table">
        <thead>
          <tr>
            <th>{t.tender.title}</th>
            <th className="sr-num">{t.reports.transactions}</th>
            <th className="sr-num">{t.common.amount}</th>
          </tr>
        </thead>
        <tbody>
          {sales.by_tender.length === 0 ? (
            <tr>
              <td colSpan={3}>{t.common.empty}</td>
            </tr>
          ) : (
            sales.by_tender.map((row) => (
              <tr key={row.method}>
                <td>{row.method_name}</td>
                <td className="sr-num">{row.count}</td>
                <td className="sr-num">{formatMoneyExact(row.amount)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* --- Түлшний төрлөөр --- */}
      <div className="sr-section">{t.shift.byFuel}</div>
      <table className="sr-table">
        <thead>
          <tr>
            <th>{t.common.code}</th>
            <th>{t.common.name}</th>
            <th className="sr-num">{t.pos.liters}</th>
            <th className="sr-num">{t.common.amount}</th>
          </tr>
        </thead>
        <tbody>
          {fuels.length === 0 ? (
            <tr>
              <td colSpan={4}>{t.common.empty}</td>
            </tr>
          ) : (
            fuels.map((row) => (
              <tr key={row.fuel_id}>
                <td>{row.code}</td>
                <td>{row.name}</td>
                <td className="sr-num">{formatLiters(row.liters, 3)}</td>
                <td className="sr-num">{formatMoneyExact(row.amount)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* --- Касс --- */}
      <div className="sr-section">{t.dashboard.cashInDrawer}</div>
      <div className="sr-grid">
        <Kv label={t.shift.openingCash} value={formatMoneyExact(cash.opening_cash)} />
        <Kv label={t.tender.cash} value={formatMoneyExact(cash.cash_sales)} />
        <Kv label={t.refunds.title} value={formatMoneyExact(cash.refunds)} />
        <Kv label={t.shift.expectedCash} value={formatMoneyExact(cash.expected_cash)} />
        <Kv label={t.shift.declaredCash} value={formatMoneyExact(cash.declared_cash)} />
        <Kv
          label={overShortLabel(cash.cash_over_short)}
          value={formatMoneyExact(cash.cash_over_short)}
        />
      </div>

      {/* --- Савны зөрүү --- */}
      <div className="sr-section">{t.shift.tankDips}</div>
      <table className="sr-table">
        <thead>
          <tr>
            <th>{t.tanks.tank}</th>
            <th>{t.tanks.fuelType}</th>
            <th className="sr-num">{t.shift.openDip}</th>
            <th className="sr-num">{t.shift.closeDip}</th>
            <th className="sr-num">{t.shift.bookLiters}</th>
            <th className="sr-num">{t.shift.variance}</th>
            <th className="sr-num">{t.shift.varianceValue}</th>
          </tr>
        </thead>
        <tbody>
          {tanks.length === 0 ? (
            <tr>
              <td colSpan={7}>{t.common.empty}</td>
            </tr>
          ) : (
            tanks.map((row) => (
              <tr key={row.tank_id}>
                <td>{row.tank_name}</td>
                <td>{row.fuel_name}</td>
                <td className="sr-num">{formatLiters(row.open_dip, 3)}</td>
                <td className="sr-num">{formatLiters(row.close_dip, 3)}</td>
                <td className="sr-num">{formatLiters(row.book_liters, 3)}</td>
                <td className="sr-num">{formatLiters(row.variance_l, 3)}</td>
                <td className="sr-num">{formatMoneyExact(row.variance_value)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* --- Тоолуур --- */}
      <div className="sr-section">{t.shift.totalizers}</div>
      <table className="sr-table">
        <thead>
          <tr>
            <th>{t.pumps.pump}</th>
            <th>{t.pumps.nozzle}</th>
            <th>{t.tanks.fuelType}</th>
            <th className="sr-num">{t.shift.openingReading}</th>
            <th className="sr-num">{t.shift.closingReading}</th>
            <th className="sr-num">{t.shift.readingDelta}</th>
            <th className="sr-num">{t.shift.soldLiters}</th>
            <th className="sr-num">{t.shift.soldAmount}</th>
          </tr>
        </thead>
        <tbody>
          {nozzles.length === 0 ? (
            <tr>
              <td colSpan={8}>{t.common.empty}</td>
            </tr>
          ) : (
            nozzles.map((row) => (
              <tr key={row.nozzle_id}>
                <td>
                  {row.pump_number} — {row.pump_name}
                </td>
                <td>{row.nozzle_number}</td>
                <td>{row.fuel_name}</td>
                <td className="sr-num">{formatLiters(row.opening_reading, 3)}</td>
                <td className="sr-num">{formatLiters(row.closing_reading, 3)}</td>
                <td className="sr-num">{formatLiters(row.reading_delta_l, 3)}</td>
                <td className="sr-num">{formatLiters(row.sold_liters, 3)}</td>
                <td className="sr-num">{formatMoneyExact(row.sold_amount)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* --- Буцаалт --- */}
      {refunds.length > 0 ? (
        <>
          <div className="sr-section">{t.refunds.title}</div>
          <table className="sr-table">
            <thead>
              <tr>
                <th>{t.sales.saleNo}</th>
                <th className="sr-num">{t.common.amount}</th>
                <th>{t.refunds.refundMethod}</th>
                <th>{t.common.status}</th>
                <th>{t.common.reason}</th>
              </tr>
            </thead>
            <tbody>
              {refunds.map((row) => (
                <tr key={row.id}>
                  <td>{row.sale_number ?? "—"}</td>
                  <td className="sr-num">{formatMoneyExact(row.amount)}</td>
                  <td>{row.refund_method_name}</td>
                  <td>{row.status_name}</td>
                  <td>{row.reason ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {/* --- Ашиг --- */}
      <div className="sr-section">{t.shift.profit}</div>
      <div className="sr-grid">
        <Kv label={t.shift.revenueNet} value={formatMoneyExact(profit.revenue_net)} />
        <Kv label={t.shift.cogs} value={formatMoneyExact(profit.cogs_total)} />
        <Kv label={t.shift.grossProfit} value={formatMoneyExact(profit.gross_profit)} />
        <Kv label={t.shift.marginPct} value={formatPct(profit.margin_pct)} />
      </div>

      {shift.note ? (
        <div className="sr-sub" style={{ marginTop: "4mm" }}>
          {t.common.note}: {shift.note}
        </div>
      ) : null}

      <div className="sr-sign">
        <span>
          {t.shift.closedBy}: ____________________ / {shift.closed_by_name ?? ""} /
        </span>
        <span>{t.common.date}: ____________________</span>
      </div>
    </div>
  );
}

export default ShiftReportTemplate;
