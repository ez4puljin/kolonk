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
import { Check, CircleCheck, Pencil, RefreshCw, TrendingDown, TrendingUp, Undo2, Wrench } from "lucide-react";

import { useBranches } from "../../api/queries/branches";
import {
  useClosingApprovalMutation,
  useCorrectClosingMutation,
  useDailyClosings,
  useRecalculateCashBulkMutation,
} from "../../api/queries/shifts";
import { useUsers } from "../../api/queries/users";
import { errorMessage } from "../../api/client";
import type { DailyClosingRow, UUID } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { CashAdjustBulkModal, CashAdjustModal } from "../../components/shift/CashAdjustModal";
import { Card } from "../../components/ui/Card";
import { Column, DataTable, WIDE_ALIGN_END, WIDE_JUSTIFY_END } from "../../components/ui/DataTable";
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
import { DateField, NumberField, PickerField, TextField } from "../catalog/_shared";

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
      opened_date: "",
      closed_date: null,
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
  /** Үнэ батлагдсан ч тэмдэглэлгүй хаасан ээлжүүдийг л харуулах. */
  const [onlyPriceHints, setOnlyPriceHints] = useState(false);
  const [editing, setEditing] = useState<DailyClosingRow | null>(null);

  const canApprove = can("shifts.approve");
  /** Зөвхөн Admin — өмнөх системийн алдаанаас үүссэн зөрүүг гараар засна. */
  const canAdjust = can("shifts.adjust");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [adjusting, setAdjusting] = useState<DailyClosingRow | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  const { data: branches } = useBranches();
  const { data: usersPage } = useUsers({ limit: 200 });
  const approval = useClosingApprovalMutation();
  const recalcBulk = useRecalculateCashBulkMutation();

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
  /** Засаж болох (батлагдаагүй, зөрүүтэй) мөрүүд — бөөнөөр сонгоход. */
  const adjustable = useMemo(
    () => rows.filter((r) => !r.approved && r.cash_over_short !== null && !dIsZero(r.cash_over_short)),
    [rows],
  );
  const selectedRows = useMemo(() => rows.filter((r) => selected.has(r.shift_id)), [rows, selected]);
  const toggle = (id: string): void =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  /** Хуучин дүрмээр бодогдсон «байвал зохих» дүнтэй ээлжүүд — батлагдаагүйг нь дахин бодно. */
  const legacyRows = useMemo(() => rows.filter((r) => r.needs_recalc), [rows]);
  const legacyEditable = useMemo(() => legacyRows.filter((r) => !r.approved), [legacyRows]);
  const priceHintCount = useMemo(() => rows.filter((r) => (r.price_hints ?? 0) > 0).length, [rows]);

  // Батлахдаа ээлжийн огноог сонгуулна (хожуу хаасан ээлжийг зөв өдөрт нь).
  const [approving, setApproving] = useState<DailyClosingRow | null>(null);
  const [approveDate, setApproveDate] = useState("");

  const setApproval = (row: DailyClosingRow, approved: boolean, businessDate?: string): void => {
    approval.mutate(
      { shiftId: row.shift_id, approved, business_date: approved ? businessDate || null : undefined },
      {
        onSuccess: () =>
          {
            toastSuccess(approved ? t.dailyClosings.approvedToast : t.dailyClosings.unapprovedToast);
            setApproving(null);
          },
        onError: (cause) => toastError(errorMessage(cause)),
      },
    );
  };

  const BADGE = {
    warning: "bg-warning-soft text-warning-dark",
    action: "bg-action-soft text-action",
    danger: "bg-danger-soft text-danger-dark",
  } as const;
  const badge = (key: string, tone: keyof typeof BADGE, text: string, title?: string) => (
    <span
      key={key}
      title={title}
      className={`inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap ${BADGE[tone]}`}
    >
      {text}
    </span>
  );
  const statusBadge = (row: DailyClosingRow) =>
    row.approved ? (
      <StatusBadge dot tone="success" size="sm" label={t.dailyClosings.approved} />
    ) : (
      <StatusBadge dot tone="warning" size="sm" label={t.dailyClosings.pending} />
    );

  const columns: Column<DailyClosingRow>[] = [
    ...(canAdjust
      ? [
          {
            key: "select",
            header: "",
            width: "2.75rem",
            hideOnMobile: true,
            render: (row: DailyClosingRow) =>
              isTotals(row) || row.approved ? null : (
                <input
                  type="checkbox"
                  aria-label={t.cashAdjust.select}
                  checked={selected.has(row.shift_id)}
                  onClick={(event) => event.stopPropagation()}
                  onChange={() => toggle(row.shift_id)}
                  className="h-5 w-5 accent-[var(--color-action)]"
                />
              ),
          } satisfies Column<DailyClosingRow>,
        ]
      : []),
    {
      // Огноо, ээлжийн дугаар, түгээгч, салбар — нэг нүдэнд (хэвтээ гүйлтгүй).
      key: "shift",
      header: t.dailyClosings.shift,
      primary: true,
      render: (row) =>
        isTotals(row) ? (
          <span className="font-black text-ink">{t.dailyClosings.grandTotal}</span>
        ) : (
          <span className="flex min-w-0 flex-col">
            <span className="num font-bold text-ink">
              {row.date}
              <span className="ml-1.5 text-xs font-semibold text-ink-faint">№{row.shift_number}</span>
            </span>
            <span className="text-[15px] font-semibold text-ink">{row.attendant || "—"}</span>
            <span className="text-xs font-normal text-ink-soft">
              {[
                row.branch_name,
                row.opened_date && row.opened_date !== row.date ? `${t.dailyClosings.openedOn}: ${row.opened_date}` : null,
                row.closed_date && row.closed_date !== row.date ? `${t.dailyClosings.closedDate}: ${row.closed_date}` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </span>
        ),
    },
    {
      key: "fuel",
      header: t.dailyClosings.fuelTotal,
      render: (row) => (
        <span className={`inline-flex flex-col ${WIDE_ALIGN_END}`}>
          <span className="font-bold">{formatMNT(row.fuel_total)}</span>
          {!dIsZero(row.credit_total ?? "0") ? (
            <span className="text-xs font-normal text-ink-soft">
              {t.dailyClosings.creditShort} {formatMNT(row.credit_total)}
            </span>
          ) : null}
        </span>
      ),
      align: "right",
      numeric: true,
    },
    {
      // Тушаалт — бэлэн, терминал, шилжүүлэг (тэгээс ялгаатайг нь).
      key: "handover",
      header: t.dailyClosings.handover,
      render: (row) => (
        <span className={`inline-flex flex-col ${WIDE_ALIGN_END}`}>
          <span className="font-bold">
            <span className="mr-1 text-xs font-semibold text-ink-faint">{t.dailyClosings.handoverCash}</span>
            {row.declared_cash === null ? "—" : formatMNT(row.declared_cash)}
          </span>
          {!dIsZero(row.settlement_total ?? "0") ? (
            <span className="text-xs font-normal text-ink-soft">
              {t.dailyClosings.handoverCard} {formatMNT(row.settlement_total)}
            </span>
          ) : null}
          {!dIsZero(row.transfer_total ?? "0") ? (
            <span className="text-xs font-normal text-ink-soft">
              {t.dailyClosings.handoverTransfer} {formatMNT(row.transfer_total)}
            </span>
          ) : null}
        </span>
      ),
      align: "right",
      numeric: true,
    },
    {
      // Зөрүү + тэмдэглэгээ: админы засвар, хуучин дүрэм, милийн зөрүү, үнийн тэмдэглэлгүй.
      key: "over_short",
      header: t.dailyClosings.overShort,
      render: (row) => {
        const value = row.cash_over_short === null ? null : dToQty(row.cash_over_short);
        const tone =
          value === null ? "text-ink-faint" : value < 0 ? "text-danger-dark" : value > 0 ? "text-warning-dark" : "text-success-dark";
        const badges = [];
        if (!isTotals(row) && row.cash_adjustment && !dIsZero(row.cash_adjustment)) {
          badges.push(
            badge("adj", "action", `${t.cashAdjust.badge}: ${formatMNT(row.cash_adjustment)}`, row.cash_adjustment_note ?? undefined),
          );
        }
        if (row.needs_recalc && row.expected_recalc && row.declared_cash !== null) {
          badges.push(
            badge("legacy", "warning", `${t.dailyClosings.legacyBadge}: ${formatMNT(dSub(row.declared_cash, row.expected_recalc))}`),
          );
        }
        if (!dIsZero(row.mile_gap_l ?? "0")) {
          badges.push(
            badge(
              "gap",
              "warning",
              t.dailyClosings.mileGapBadge.replace(
                "{gap}",
                `${dToQty(row.mile_gap_l) > 0 ? "+" : ""}${formatLiters(row.mile_gap_l, 3)}`,
              ),
              t.dailyClosings.mileGapTip.replace("{n}", String(row.mile_gap_nozzles ?? 0)),
            ),
          );
        }
        if (!isTotals(row) && (row.price_hints ?? 0) > 0) {
          badges.push(badge("price", "danger", t.dailyClosings.priceHint, t.dailyClosings.priceHintTip));
        }
        return (
          <span className={`inline-flex flex-col gap-1 ${WIDE_ALIGN_END}`}>
            <span className={`font-bold ${tone}`}>{row.cash_over_short === null ? "—" : formatMNT(row.cash_over_short)}</span>
            {badges.length > 0 ? <span className={`flex flex-wrap gap-1 ${WIDE_JUSTIFY_END}`}>{badges}</span> : null}
          </span>
        );
      },
      align: "right",
      numeric: true,
    },
  ];

  // Батлах эрхгүй (зөвхөн харах) хэрэглэгчид төлөв тусдаа багана.
  if (!(canApprove || canAdjust)) {
    columns.push({
      key: "status",
      header: t.dailyClosings.status,
      render: (row) => (isTotals(row) ? null : statusBadge(row)),
    });
  }

  /**
   * Үйлдэл — хүснэгтэд дүрстэй жижиг товч (үргэлж харагдана), картанд бичигтэй.
   * Батлагдсан мөрөнд төлөв + буцаах товч.
   */
  const actionButtons = (row: DailyClosingRow, labels: boolean) => {
    if (isTotals(row)) return null;
    const wrap = labels ? "flex flex-wrap items-center gap-2" : "flex items-center justify-end gap-1.5 whitespace-nowrap";
    if (row.approved) {
      return (
        <div className={wrap} onClick={(event) => event.stopPropagation()} role="presentation">
          {statusBadge(row)}
          {canApprove ? (
            <Button
              variant="secondary"
              size="sm"
              icon={<Undo2 />}
              onClick={() => setApproval(row, false)}
              aria-label={t.dailyClosings.unapprove}
              title={t.dailyClosings.unapprove}
            >
              {labels ? t.dailyClosings.unapprove : null}
            </Button>
          ) : null}
        </div>
      );
    }
    return (
      <div className={wrap} onClick={(event) => event.stopPropagation()} role="presentation">
        {canAdjust ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<Wrench />}
            onClick={() => setAdjusting(row)}
            aria-label={t.cashAdjust.action}
            title={t.cashAdjust.action}
          >
            {labels ? t.cashAdjust.actionShort : null}
          </Button>
        ) : null}
        {canApprove ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<Pencil />}
            onClick={() => setEditing(row)}
            aria-label={t.dailyClosings.correct}
            title={t.dailyClosings.correct}
          >
            {labels ? t.dailyClosings.correct : null}
          </Button>
        ) : null}
        {canApprove ? (
          <Button
            variant="success"
            size="sm"
            icon={<CircleCheck />}
            onClick={() => {
              setApproveDate(row.date);
              setApproving(row);
            }}
          >
            {t.dailyClosings.approve}
          </Button>
        ) : null}
      </div>
    );
  };

  if (canApprove || canAdjust) {
    columns.push({
      key: "actions",
      header: t.dailyClosings.actions,
      render: (row) => actionButtons(row, false),
      renderCard: (row) => actionButtons(row, true),
      align: "right",
    });
  }

  const visibleRows = useMemo(
    () => (onlyPriceHints ? rows.filter((r) => (r.price_hints ?? 0) > 0) : rows),
    [rows, onlyPriceHints],
  );
  const tableRows = useMemo(() => withTotalsRow(visibleRows), [visibleRows]);

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

      {legacyRows.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-2 border-warning bg-warning-soft px-4 py-3 text-warning-dark">
          <span className="min-w-0 flex-1 text-sm">
            {t.dailyClosings.legacyBanner.replace("{n}", String(legacyRows.length))}
            {legacyRows.length > legacyEditable.length
              ? ` ${t.dailyClosings.legacyApproved.replace("{n}", String(legacyRows.length - legacyEditable.length))}`
              : ""}
          </span>
          {canApprove && legacyEditable.length > 0 ? (
            <Button
              variant="warning"
              size="md"
              icon={<RefreshCw />}
              loading={recalcBulk.isPending}
              onClick={() =>
                recalcBulk.mutate(
                  legacyEditable.map((r) => r.shift_id),
                  {
                    onSuccess: (result) =>
                      toastSuccess(t.dailyClosings.legacyDone.replace("{n}", String(result.recalculated.length))),
                    onError: (cause) => toastError(errorMessage(cause)),
                  },
                )
              }
            >
              {t.dailyClosings.legacyRecalc.replace("{n}", String(legacyEditable.length))}
            </Button>
          ) : null}
        </div>
      ) : null}

      {priceHintCount > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-2 border-danger bg-danger-soft px-4 py-3 text-danger-dark">
          <span className="min-w-0 flex-1 text-sm">
            {t.dailyClosings.priceHintBanner.replace("{n}", String(priceHintCount))}
          </span>
          <Button variant="secondary" size="md" onClick={() => setOnlyPriceHints((value) => !value)}>
            {onlyPriceHints ? t.dailyClosings.priceHintAll : t.dailyClosings.priceHintOnly}
          </Button>
        </div>
      ) : null}

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

      {canAdjust && adjustable.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-white px-4 py-3">
          <span className="min-w-0 flex-1 text-sm text-ink-soft">
            {t.cashAdjust.toolbarHint.replace("{n}", String(adjustable.length))}
          </span>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="md"
              onClick={() =>
                setSelected(
                  selected.size > 0 ? new Set() : new Set(adjustable.map((r) => r.shift_id)),
                )
              }
            >
              {selected.size > 0 ? t.cashAdjust.clearSelection : t.cashAdjust.selectAll}
            </Button>
            <Button
              variant="primary"
              size="md"
              icon={<Wrench />}
              disabled={selectedRows.length === 0}
              onClick={() => setBulkOpen(true)}
            >
              {t.cashAdjust.bulkAction.replace("{n}", String(selectedRows.length))}
            </Button>
          </div>
        </div>
      ) : null}

      <DataTable
        columns={columns}
        rows={tableRows}
        rowKey={(row) => row.shift_id}
        stack="wide"
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
      {canAdjust ? (
        <>
          <CashAdjustModal
            shiftId={adjusting?.shift_id ?? null}
            open={adjusting !== null}
            onClose={() => setAdjusting(null)}
            subtitle={adjusting ? `${adjusting.date} · ${adjusting.attendant} · ${adjusting.branch_name}` : undefined}
          />
          <CashAdjustBulkModal
            rows={selectedRows}
            open={bulkOpen}
            onClose={() => setBulkOpen(false)}
            onDone={() => setSelected(new Set())}
          />
        </>
      ) : null}
      <Modal
        open={approving !== null}
        onClose={() => setApproving(null)}
        size="sm"
        title={t.dailyClosings.approve}
        subtitle={approving ? `${approving.attendant} · ${approving.branch_name}` : undefined}
        dismissible={!approval.isPending}
        footer={
          <>
            <Button variant="secondary" size="md" disabled={approval.isPending} onClick={() => setApproving(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="success"
              size="md"
              icon={<CircleCheck />}
              loading={approval.isPending}
              disabled={approveDate === ""}
              onClick={() => approving && setApproval(approving, true, approveDate)}
            >
              {t.dailyClosings.approve}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <DateField
            label={t.dailyClosings.approveDate}
            value={approveDate}
            onChange={setApproveDate}
            max={approving?.opened_date}
          />
          <p className="text-xs text-ink-soft">{t.dailyClosings.approveDateHint}</p>
          {approving ? (
            <p className="num text-xs text-ink-soft">
              {t.dailyClosings.openedOn}: {approving.opened_date}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default DailyClosingsPage;
