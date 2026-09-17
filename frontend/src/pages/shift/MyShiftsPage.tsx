/**
 * Миний ээлжүүд — түгээгч зөвхөн ӨӨРИЙН нээж, хаасан ээлжүүдээ харж, тайланг нь нээнэ.
 *
 * Сервер `GET /shifts` дээр «бүх ээлж харах» эрхгүй хэрэглэгчид зөвхөн өөрийн
 * ээлжийг буцаадаг тул энд нэмэлт шүүлт хэрэггүй.
 */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { FileText } from "lucide-react";

import { useShifts } from "../../api/queries/shifts";
import type { ShiftSummary } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { SHIFT_STATUS_META, statusMeta } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { formatDateTime, formatMNT } from "../../lib/format";

export function MyShiftsPage() {
  const navigate = useNavigate();
  const query = useShifts({ limit: 100 });
  const rows = useMemo(() => query.data?.items ?? [], [query.data]);
  const closed = useMemo(() => rows.filter((row) => row.status === "closed"), [rows]);
  const overShortTotal = useMemo(() => dSum(closed.map((row) => row.cash_over_short ?? "0")), [closed]);

  const columns: Column<ShiftSummary>[] = [
    {
      key: "number",
      header: t.shift.number,
      primary: true,
      render: (row) => <span className="num font-bold">№{row.number}</span>,
    },
    { key: "opened", header: t.myShifts.openedAt, numeric: true, render: (row) => formatDateTime(row.opened_at) },
    {
      key: "closed",
      header: t.myShifts.closedAt,
      numeric: true,
      render: (row) => (row.closed_at ? formatDateTime(row.closed_at) : "—"),
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(SHIFT_STATUS_META, row.status, row.status_name)} />,
    },
    {
      key: "expected",
      header: t.shift.expectedCash,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.expected_cash != null ? formatMNT(row.expected_cash) : "—"),
    },
    {
      key: "declared",
      header: t.shift.declaredCash,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.declared_cash != null ? formatMNT(row.declared_cash) : "—"),
    },
    {
      key: "diff",
      header: t.shift.overShort,
      align: "right",
      numeric: true,
      render: (row) =>
        row.cash_over_short != null ? (
          <span className={`font-bold ${Number(row.cash_over_short) < 0 ? "text-danger-dark" : Number(row.cash_over_short) > 0 ? "text-warning-dark" : "text-ink"}`}>
            {formatMNT(row.cash_over_short)}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "action",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <Button
          variant="secondary"
          size="md"
          icon={<FileText className="h-5 w-5" />}
          onClick={() => navigate(`/shift/report/${row.id}`)}
        >
          {t.myShifts.report}
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.myShifts.title} subtitle={t.myShifts.subtitle} />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.myShifts.total} value={rows.length} tone="neutral" />
        <StatBox label={t.myShifts.closedCount} value={closed.length} tone="action" />
        <StatBox
          label={t.shift.overShort}
          value={formatMNT(overShortTotal)}
          tone={Number(overShortTotal) < 0 ? "danger" : "success"}
        />
      </div>
      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={query.isLoading}
          emptyTitle={t.common.empty}
          onRowClick={(row) => navigate(`/shift/report/${row.id}`)}
        />
      </Card>
    </div>
  );
}

export default MyShiftsPage;
