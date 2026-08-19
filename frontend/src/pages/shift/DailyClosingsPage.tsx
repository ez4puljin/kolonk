/**
 * Ээлжийн тайлан — нягтлангийн хяналтын дэлгэц.
 *
 * Салбар бүрийн түгээгчийн хаагдсан ээлжүүдийг огноо, салбар, ажилтан,
 * батламжийн төлвөөр шүүж, кассын илүүдэл/дутагдлыг хянана. Буруу тоолсон
 * бэлэн мөнгийг засахад зөрүүний журналын бичилт дахин хийгдэж, батласны
 * дараа хаалт түгжигдэнэ.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, CircleCheck, Pencil, TrendingDown, TrendingUp, Undo2 } from "lucide-react";

import { useBranches } from "../../api/queries/branches";
import {
  useClosingApprovalMutation,
  useCorrectClosingMutation,
  useDailyClosings,
} from "../../api/queries/shifts";
import { useUsers } from "../../api/queries/users";
import { errorMessage } from "../../api/client";
import type { DailyClosingRow, UUID } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Column, DataTable } from "../../components/ui/DataTable";
import { DateRangePicker } from "../../components/ui/DateRangePicker";
import { Modal } from "../../components/ui/Modal";
import { MultiSelect } from "../../components/ui/MultiSelect";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { dAbs, dIsZero, dSub, dSum, dToQty } from "../../lib/decimal";
import { formatLiters, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, PickerField, TextField } from "../catalog/_shared";

type StatusFilter = "" | "approved" | "pending";

/** Хөл дүрийн зохиомол мөрийн түлхүүр — жинхэнэ ээлжийн id-тэй давхцахгүй. */
const TOTALS_KEY = "__totals__";

/**
 * Хүснэгтийн мөрүүдийн доор хөл дүн нэмнэ.
 *
 * Тусад нь блок болгож бичвэл багана бүртэй эгнэхгүй тул нягтлан аль дүн
 * аль баганых болохыг нүдээрээ тааруулах хэрэгтэй болно. Иймд жинхэнэ мөр
 * болгож нэмээд өнгөөр нь ялгана.
 */
function withTotalsRow(rows: readonly DailyClosingRow[]): DailyClosingRow[] {
  if (rows.length === 0) return [...rows];
  const sumOf = (pick: (row: DailyClosingRow) => string | null): string =>
    dSum(rows.map((row) => pick(row) ?? "0"));
  return [
    ...rows,
    {
      shift_id: TOTALS_KEY,
      shift_number: 0,
      date: "",
      attendant: "",
      opening_cash: sumOf((row) => row.opening_cash),
      fuel_total: sumOf((row) => row.fuel_total),
      credit_total: sumOf((row) => row.credit_total),
      oil_total: sumOf((row) => row.oil_total),
      settlement_total: sumOf((row) => row.settlement_total),
      transfer_total: sumOf((row) => row.transfer_total),
      declared_cash: sumOf((row) => row.declared_cash),
      expected_cash: sumOf((row) => row.expected_cash),
      cash_over_short: sumOf((row) => row.cash_over_short),
      // Милийн зөрүүг АБСОЛЮТ дүнгээр нэмнэ: нэг ээлж +10 л, нөгөө нь −10 л
      // байхад тэмдэгтэй нийлбэр 0 гарч, хоёр зөрчил хоёулаа нуугдана.
      mile_gap_l: dSum(rows.map((row) => dAbs(row.mile_gap_l ?? "0"))),
      mile_gap_nozzles: rows.reduce((acc, row) => acc + (row.mile_gap_nozzles ?? 0), 0),
      attendant_id: null,
      branch_id: null,
      branch_name: "",
      approved: false,
      approved_at: null,
      approved_by_name: "",
      approval_note: null,
      note: null,
    },
  ];
}

const isTotals = (row: DailyClosingRow): boolean => row.shift_id === TOTALS_KEY;

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

// --------------------------------------------------------------------------
// Зөрүү засах цонх
// --------------------------------------------------------------------------
function CorrectModal({
  row,
  open,
  onClose,
}: {
  row: DailyClosingRow | null;
  open: boolean;
  onClose: () => void;
}) {
  const correct = useCorrectClosingMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const [declared, setDeclared] = useState("");
  const [note, setNote] = useState("");
  const [ready, setReady] = useState<string | null>(null);

  // Цонх нээгдэх бүрд одоогийн дүнгээр урьдчилан бөглөнө.
  if (open && row && ready !== row.shift_id) {
    setReady(row.shift_id);
    setDeclared(row.declared_cash ?? "0");
    setNote("");
  }

  const expected = row?.expected_cash ?? "0";
  const nextDiff = dSub(declared === "" ? "0" : declared, expected);

  return (
    <Modal
      open={open && row !== null}
      onClose={onClose}
      size="md"
      title={t.dailyClosings.correctTitle}
      subtitle={row ? `${row.date} · ${row.attendant} · ${row.branch_name}` : undefined}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Check />}
            loading={correct.isPending}
            onClick={() => {
              if (!row) return;
              correct.mutate(
                { shiftId: row.shift_id, declaredCash: declared === "" ? "0" : declared, note },
                {
                  onSuccess: () => {
                    toastSuccess(t.dailyClosings.correctedToast);
                    setReady(null);
                    onClose();
                  },
                  onError: (cause) => toastError(errorMessage(cause)),
                },
              );
            }}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{t.dailyClosings.correctHint}</p>

        <div className="num flex items-baseline justify-between rounded-xl border border-line bg-surface-alt px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.shift.expectedCash}</span>
          <span className="text-lg font-bold text-ink">{formatMNT(expected)}</span>
        </div>

        <NumberField
          name="correct-declared"
          label={t.shift.declaredCash}
          value={declared}
          onChange={setDeclared}
          suffix={t.units.mnt}
        />

        <div className="num flex items-baseline justify-between rounded-xl border border-line-strong px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.shift.overShort}</span>
          <span
            className={[
              "text-xl font-black",
              dToQty(nextDiff) < 0
                ? "text-danger-dark"
                : dToQty(nextDiff) > 0
                  ? "text-warning-dark"
                  : "text-success-dark",
            ].join(" ")}
          >
            {formatMNT(nextDiff)}
          </span>
        </div>

        <TextField label={t.dailyClosings.approvalNote} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Үндсэн хуудас
// --------------------------------------------------------------------------
export function DailyClosingsPage() {
  const navigate = useNavigate();
  const { can } = usePermission();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [dateFrom, setDateFrom] = useState(monthStartIso);
  const [dateTo, setDateTo] = useState(todayIso);
  const [branchIds, setBranchIds] = useState<UUID[]>([]);
  const [attendantIds, setAttendantIds] = useState<UUID[]>([]);
  const [status, setStatus] = useState<StatusFilter>("");
  const [onlyVariance, setOnlyVariance] = useState(false);
  const [editing, setEditing] = useState<DailyClosingRow | null>(null);

  const canApprove = can("shifts.approve");

  const { data: branches } = useBranches();
  const { data: usersPage } = useUsers({ limit: 200 });
  const approval = useClosingApprovalMutation();

  const listQuery = useDailyClosings({
    date_from: dateFrom,
    date_to: dateTo,
    branch_id: branchIds.length ? branchIds : undefined,
    attendant_id: attendantIds.length ? attendantIds : undefined,
    status: status === "" ? undefined : status,
    only_variance: onlyVariance || undefined,
  });
  const rows = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  const branchOptions = useMemo(
    () => (branches ?? []).map((b) => ({ value: b.id, label: b.name })),
    [branches],
  );
  // Ээлж нээдэг хүмүүс = түгээгч; менежер/эзэн ч хаалт хийж болно.
  const attendantOptions = useMemo(
    () => (usersPage?.items ?? []).map((u) => ({ value: u.id, label: u.full_name })),
    [usersPage],
  );

  const overSum = useMemo(
    () =>
      dSum(
        rows
          .map((r) => r.cash_over_short ?? "0")
          .filter((v) => dToQty(v) > 0),
      ),
    [rows],
  );
  const shortSum = useMemo(
    () =>
      dSum(
        rows
          .map((r) => r.cash_over_short ?? "0")
          .filter((v) => dToQty(v) < 0),
      ),
    [rows],
  );
  const pendingCount = useMemo(() => rows.filter((r) => !r.approved).length, [rows]);

  const setApproval = (row: DailyClosingRow, approved: boolean): void => {
    approval.mutate(
      { shiftId: row.shift_id, approved },
      {
        onSuccess: () =>
          toastSuccess(
            approved ? t.dailyClosings.approvedToast : t.dailyClosings.unapprovedToast,
          ),
        onError: (cause) => toastError(errorMessage(cause)),
      },
    );
  };

  const columns: Column<DailyClosingRow>[] = [
    {
      key: "date",
      header: t.dailyClosings.date,
      render: (row) =>
        isTotals(row) ? (
          // Утсанд карт болох тул гарчиг нь `attendant` багана — давхар
          // бичихгүйн тулд энд зөвхөн ширээний дэлгэцэд гаргана.
          <span className="hidden font-black text-ink md:inline">{t.dailyClosings.grandTotal}</span>
        ) : (
          <span className="num">{row.date}</span>
        ),
      width: "7rem",
    },
    {
      key: "branch",
      header: t.dailyClosings.branch,
      render: (row) => (isTotals(row) ? "" : row.branch_name || "—"),
      hideOnMobile: true,
    },
    {
      key: "attendant",
      header: t.dailyClosings.attendant,
      render: (row) =>
        isTotals(row) ? (
          <span className="font-black text-ink md:hidden">{t.dailyClosings.grandTotal}</span>
        ) : (
          row.attendant || "—"
        ),
      primary: true,
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
      key: "settlement",
      header: t.dailyClosings.settlementTotal,
      render: (row) => formatMNT(row.settlement_total),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "transfer",
      header: t.dailyClosings.transferTotal,
      render: (row) => formatMNT(row.transfer_total ?? "0"),
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
      // Миль хуримтлагдсан заалт тул өмнөх хаалттай ЯГ тэнцүү байх ёстой.
      key: "mile_gap",
      header: t.dailyClosings.mileGap,
      render: (row) => {
        if (dIsZero(row.mile_gap_l ?? "0")) {
          return <span className="text-ink-faint">0</span>;
        }
        return (
          <span className="font-bold text-warning-dark">
            {dToQty(row.mile_gap_l) > 0 ? "+" : ""}
            {formatLiters(row.mile_gap_l, 3)}
          </span>
        );
      },
      align: "right",
      numeric: true,
    },
    {
      key: "over_short",
      header: t.dailyClosings.overShort,
      render: (row) => {
        if (row.cash_over_short === null) return "—";
        const value = dToQty(row.cash_over_short);
        const tone =
          value < 0 ? "text-danger-dark" : value > 0 ? "text-warning-dark" : "text-success-dark";
        return <span className={`font-bold ${tone}`}>{formatMNT(row.cash_over_short)}</span>;
      },
      align: "right",
      numeric: true,
    },
    {
      key: "status",
      header: t.dailyClosings.status,
      render: (row) =>
        isTotals(row) ? null : row.approved ? (
          <StatusBadge
            dot
            tone="success"
            size="sm"
            label={t.dailyClosings.approved}
          />
        ) : (
          <StatusBadge dot tone="warning" size="sm" label={t.dailyClosings.pending} />
        ),
    },
  ];

  if (canApprove) {
    columns.push({
      key: "actions",
      header: "",
      render: (row) =>
        isTotals(row) ? null : (
        <div
          className="flex justify-end gap-2"
          onClick={(event) => event.stopPropagation()}
          role="presentation"
        >
          {row.approved ? (
            <Button
              variant="secondary"
              size="md"
              icon={<Undo2 />}
              onClick={() => setApproval(row, false)}
            >
              {t.dailyClosings.unapprove}
            </Button>
          ) : (
            <>
              <Button
                variant="secondary"
                size="md"
                icon={<Pencil />}
                onClick={() => setEditing(row)}
              >
                {t.dailyClosings.correct}
              </Button>
              <Button
                variant="success"
                size="md"
                icon={<CircleCheck />}
                onClick={() => setApproval(row, true)}
              >
                {t.dailyClosings.approve}
              </Button>
            </>
          )}
        </div>
      ),
      align: "right",
    });
  }

  const tableRows = useMemo(() => withTotalsRow(rows), [rows]);

  return (
    <div className="flex flex-col gap-4 sm:gap-5">
      <header>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">{t.dailyClosings.title}</h1>
        <p className="text-[13px] text-ink-soft sm:text-sm">{t.dailyClosings.subtitle}</p>
      </header>

      <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-2 lg:grid-cols-4">
        <StatBox
          label={t.dailyClosings.totalShort}
          value={formatMNT(shortSum)}
          icon={<TrendingDown />}
          tone="danger"
        />
        <StatBox
          label={t.dailyClosings.totalOver}
          value={formatMNT(overSum)}
          icon={<TrendingUp />}
          tone="warning"
        />
        <StatBox label={t.dailyClosings.pendingCount} value={pendingCount} tone="action" />
        <StatBox label={t.dailyClosings.periodCount} value={rows.length} />
      </div>

      <Card>
        <div className="flex flex-col gap-3">
          <DateRangePicker
            value={{ from: dateFrom, to: dateTo }}
            onChange={(range) => {
              setDateFrom(range.from);
              setDateTo(range.to);
            }}
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MultiSelect
              label={t.dailyClosings.branch}
              values={branchIds}
              onChange={setBranchIds}
              options={branchOptions}
            />
            <MultiSelect
              label={t.dailyClosings.attendant}
              values={attendantIds}
              onChange={setAttendantIds}
              options={attendantOptions}
            />
            <PickerField
              label={t.dailyClosings.status}
              value={status}
              options={[
                { value: "", label: t.common.all },
                { value: "pending", label: t.dailyClosings.pending },
                { value: "approved", label: t.dailyClosings.approved },
              ]}
              onChange={(value) => setStatus(value as StatusFilter)}
              searchable={false}
            />
          </div>
          <label className="flex min-h-11 items-center gap-3 text-[15px] font-medium text-ink">
            <input
              type="checkbox"
              checked={onlyVariance}
              onChange={(event) => setOnlyVariance(event.target.checked)}
              className="h-5 w-5 accent-[var(--color-action)]"
            />
            {t.dailyClosings.onlyVariance}
          </label>
        </div>
      </Card>

      <DataTable
        columns={columns}
        rows={tableRows}
        rowKey={(row) => row.shift_id}
        loading={listQuery.isLoading}
        emptyTitle={t.dailyClosings.empty}
        rowClassName={(row) => (isTotals(row) ? "bg-surface-alt font-bold" : "")}
        onRowClick={(row) => {
          // Хөл дүн бол жинхэнэ ээлж биш — тайлан руу орох зүйлгүй.
          if (isTotals(row)) return;
          navigate(`/shift/report/${row.shift_id}`);
        }}
      />

      <CorrectModal row={editing} open={editing !== null} onClose={() => setEditing(null)} />
    </div>
  );
}

export default DailyClosingsPage;
