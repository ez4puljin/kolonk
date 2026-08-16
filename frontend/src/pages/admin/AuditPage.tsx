import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, ScrollText } from "lucide-react";

import { useAuditLogs } from "../../api/queries/system";
import { useUsers } from "../../api/queries/users";
import type { AuditLog, JsonValue } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { daysAgoInput, formatDateTime, todayInput } from "../../lib/format";
import { Pager, PickerField, SearchInput, useDebounced } from "../catalog/_shared";

/** Дурын JSON утгыг богино текст болгоно. */
function renderValue(value: JsonValue | undefined): string {
  if (value === undefined || value === null) return "—";
  if (typeof value === "string") return value === "" ? "—" : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

interface DiffRow {
  key: string;
  before: string;
  after: string;
  changed: boolean;
}

function diffRows(log: AuditLog): DiffRow[] {
  const before = log.before ?? {};
  const after = log.after ?? {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();
  return keys.map((key) => {
    const beforeText = renderValue(before[key]);
    const afterText = renderValue(after[key]);
    return { key, before: beforeText, after: afterText, changed: beforeText !== afterText };
  });
}

export function AuditPage() {
  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(6), to: todayInput() });
  const [userId, setUserId] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const debouncedAction = useDebounced(action);
  const debouncedEntity = useDebounced(entityType);

  const usersQuery = useUsers({ limit: 200 });
  const logsQuery = useAuditLogs({
    date_from: range.from,
    date_to: range.to,
    user_id: userId || undefined,
    action: debouncedAction || undefined,
    entity_type: debouncedEntity || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const rows = useMemo(() => logsQuery.data?.items ?? [], [logsQuery.data]);
  const total = logsQuery.data?.total ?? 0;

  const userOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...(usersQuery.data?.items ?? []).map((user) => ({
        value: user.id,
        label: user.full_name,
        hint: user.username,
      })),
    ],
    [usersQuery.data],
  );

  const columns: Column<AuditLog>[] = [
    {
      key: "created_at",
      header: t.common.dateTime,
      primary: true,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    { key: "user", header: t.common.user, render: (row) => row.user_full_name ?? "—" },
    {
      key: "action",
      header: t.admin.action,
      render: (row) => <StatusBadge size="sm" tone="action" label={row.action} />,
    },
    {
      key: "entity",
      header: t.admin.entity,
      hideOnMobile: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="text-sm font-semibold text-ink">{row.entity_type ?? "—"}</span>
          <span className="num text-xs text-ink-faint">{row.entity_id ?? ""}</span>
        </span>
      ),
    },
    { key: "ip", header: t.admin.ip, numeric: true, hideOnMobile: true, render: (row) => row.ip ?? "—" },
    {
      key: "expand",
      header: t.common.details,
      align: "right",
      hideOnMobile: true,
      render: (row) => (
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-action-dark">
          {expanded === row.id ? t.common.less : t.common.more}
          {expanded === row.id ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
      ),
    },
  ];

  const expandedLog = rows.find((row) => row.id === expanded) ?? null;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.admin.audit} subtitle={t.nav.audit} />

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
            label={t.common.user}
            value={userId}
            options={userOptions}
            onChange={(next) => {
              setUserId(next);
              setOffset(0);
            }}
            className="min-w-[15rem]"
          />
          <SearchInput
            value={action}
            onChange={(next) => {
              setAction(next);
              setOffset(0);
            }}
            placeholder={t.admin.action}
          />
          <SearchInput
            value={entityType}
            onChange={(next) => {
              setEntityType(next);
              setOffset(0);
            }}
            placeholder={t.admin.entity}
          />
        </div>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={(row) => setExpanded((current) => (current === row.id ? null : row.id))}
          loading={logsQuery.isLoading}
          rowClassName={(row) => (row.id === expanded ? "bg-action-soft/40" : "")}
          empty={
            <EmptyState icon={<ScrollText className="h-7 w-7" />} title={t.common.empty} hint={t.common.emptyHint} />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      {expandedLog ? (
        <Card
          title={expandedLog.action}
          subtitle={`${expandedLog.entity_type ?? "—"} · ${formatDateTime(expandedLog.created_at)}`}
        >
          <div className="scroll-touch overflow-x-auto">
            <table className="w-full min-w-[36rem] border-collapse text-[15px]">
              <thead>
                <tr className="border-b border-line-strong bg-surface-alt">
                  <th className="px-3 py-2.5 text-left text-xs font-bold text-ink-soft uppercase">
                    {t.common.name}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-bold text-ink-soft uppercase">
                    {t.admin.before}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-bold text-ink-soft uppercase">
                    {t.admin.after}
                  </th>
                </tr>
              </thead>
              <tbody>
                {diffRows(expandedLog).length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-ink-soft">
                      {t.common.empty}
                    </td>
                  </tr>
                ) : (
                  diffRows(expandedLog).map((row) => (
                    <tr key={row.key} className="border-b border-line last:border-b-0">
                      <td className="px-3 py-2.5 font-semibold text-ink">{row.key}</td>
                      <td
                        className={`num px-3 py-2.5 break-all ${row.changed ? "bg-danger-soft/50 text-danger-dark" : "text-ink-soft"}`}
                      >
                        {row.before}
                      </td>
                      <td
                        className={`num px-3 py-2.5 break-all ${row.changed ? "bg-success-soft/60 font-semibold text-success-dark" : "text-ink-soft"}`}
                      >
                        {row.after}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

export default AuditPage;
