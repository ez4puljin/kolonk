/**
 * Цалингийн тооцоо — энгийн, алхам алхмаар.
 *
 * Дэлгэцийн бүтэц (дээрээс доош):
 *   1. Сарын сонголт — байгаа саруудын жижиг товчнууд + "Шинэ сар"
 *   2. Гурван том тоо — цалингийн сан, гарт олгох, компанид тусах зардал
 *   3. Дараагийн алхмын зурвас — яг одоо юу хийхийг нэг өгүүлбэрээр хэлнэ
 *   4. Ажилтны жагсаалт — мөр дээр дарж засна
 *
 * Хувь хэмжээ, өглөгийн задаргаа зэрэг нарийн мэдээллийг нуруу болгож,
 * хэрэгтэй үед нь л дэлгэнэ.
 */

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  Coins,
  Info,
  Plus,
  RefreshCw,
  SlidersHorizontal,
  Trash2,
  Wallet,
} from "lucide-react";

import { useEmployees } from "../../api/queries/payroll";
import { useSettings, useUpdateSettingMutation } from "../../api/queries/system";
import {
  useApprovePayrollMutation,
  useCancelPeriodMutation,
  useCreatePeriodMutation,
  usePayPayrollMutation,
  usePayrollPeriod,
  usePayrollPeriods,
  useRecalculatePayrollMutation,
  useUpdatePayrollLineMutation,
} from "../../api/queries/payroll";
import type { PayrollLine, UUID } from "../../api/types";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TouchSelect } from "../../components/ui/TouchSelect";
import { t } from "../../i18n/mn";
import { formatDate, formatMNT, formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { TextField } from "../catalog/_shared";

const MONTHS = [
  "1-р сар", "2-р сар", "3-р сар", "4-р сар", "5-р сар", "6-р сар",
  "7-р сар", "8-р сар", "9-р сар", "10-р сар", "11-р сар", "12-р сар",
];

const STATUS_TONE: Record<string, "neutral" | "action" | "success"> = {
  draft: "neutral",
  approved: "action",
  paid: "success",
};

/** Мөр засах талбарууд — NumPad-аар оруулна. */
const EDIT_FIELDS = [
  { key: "worked_days", label: t.payroll.workedDays, money: false },
  { key: "bonus", label: t.payroll.bonus, money: true },
  { key: "advance", label: t.payroll.advance, money: true },
  { key: "other_deduction", label: t.payroll.otherDeduction, money: true },
] as const;

export function PayrollPage() {
  const now = new Date();
  const [periodId, setPeriodId] = useState<UUID | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [newYear, setNewYear] = useState(now.getFullYear());
  const [newMonth, setNewMonth] = useState(now.getMonth() + 1);
  const [editLine, setEditLine] = useState<PayrollLine | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [payTarget, setPayTarget] = useState<string | null>(null);
  const [showRates, setShowRates] = useState(false);
  /** Шинэ сарын ажилтны сонголт — хоосон бол бүгд орно. */
  const [pickedEmployees, setPickedEmployees] = useState<string[]>([]);
  const [ratesOpen, setRatesOpen] = useState(false);
  const [rateDraft, setRateDraft] = useState<Record<string, string>>({});
  const [rateError, setRateError] = useState<string | null>(null);

  const periodsQuery = usePayrollPeriods();
  const periodQuery = usePayrollPeriod(periodId);
  const createMutation = useCreatePeriodMutation();
  const updateLineMutation = useUpdatePayrollLineMutation();
  const recalcMutation = useRecalculatePayrollMutation();
  const approveMutation = useApprovePayrollMutation();
  const cancelMutation = useCancelPeriodMutation();
  const employeesQuery = useEmployees({ is_active: true });
  const settingsQuery = useSettings();
  const updateSetting = useUpdateSettingMutation();
  const payMutation = usePayPayrollMutation();

  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const periods = useMemo(() => periodsQuery.data?.items ?? [], [periodsQuery.data]);
  const period = periodQuery.data;

  useEffect(() => {
    if (!periodId && periods.length > 0) setPeriodId(periods[0].id);
  }, [periods, periodId]);

  const employees = useMemo(() => employeesQuery.data?.items ?? [], [employeesQuery.data]);

  /** Тохиргооны түлхүүр → шошго. Хувийг % болгож харуулна. */
  const RATE_FIELDS = useMemo(
    () => [
      { key: "payroll_si_employee_rate", label: t.payroll.siEmployeeRate, pct: true },
      { key: "payroll_si_employer_rate", label: t.payroll.siEmployerRate, pct: true },
      { key: "payroll_pit_rate", label: t.payroll.pitRate, pct: true },
      { key: "payroll_pit_credit", label: t.payroll.pitCredit, pct: false },
    ],
    [],
  );

  const openRates = (): void => {
    const cfg = settingsQuery.data ?? {};
    const draft: Record<string, string> = {};
    for (const field of RATE_FIELDS) {
      const raw = String(cfg[field.key] ?? "0");
      // Хувийг 0.115 → "11.5" болгож харуулна — хэрэглэгч % -аар бодно.
      draft[field.key] = field.pct ? String(Number(raw) * 100) : raw;
    }
    setRateDraft(draft);
    setRateError(null);
    setRatesOpen(true);
  };

  const saveRates = async (): Promise<void> => {
    setRateError(null);
    try {
      for (const field of RATE_FIELDS) {
        const typed = (rateDraft[field.key] ?? "").trim();
        if (typed === "") continue;
        const value = field.pct ? String(Number(typed) / 100) : typed;
        await updateSetting.mutateAsync({ key: field.key, value });
      }
      toastSuccess(t.common.saved);
      setRatesOpen(false);
    } catch (error) {
      setRateError(error instanceof Error ? error.message : t.common.error);
    }
  };

  const isDraft = period?.status === "draft";
  const isPaid = period?.status === "paid";

  const fail = (e: unknown): void => {
    toastError(e instanceof Error ? e.message : t.common.error);
  };

  const createPeriod = (): void => {
    createMutation.mutate(
      {
        year: newYear,
        month: newMonth,
        employee_ids: pickedEmployees.length > 0 ? (pickedEmployees as never) : null,
      },
      {
        onSuccess: (created) => {
          setPeriodId(created.id);
          setNewOpen(false);
          setPickedEmployees([]);
          toastSuccess(`${created.label} — ${t.payroll.calculated}`);
        },
        onError: fail,
      },
    );
  };

  const saveField = (field: string, value: string): void => {
    if (!editLine) return;
    updateLineMutation.mutate(
      { id: editLine.id, [field]: value },
      {
        onSuccess: (updated) => {
          const fresh = updated.lines.find((l) => l.id === editLine.id);
          if (fresh) setEditLine(fresh);
        },
        onError: fail,
      },
    );
  };

  /** Тухайн мөрд НДШ бодох эсэхийг солино — бусад тооцоо шууд шинэчлэгдэнэ. */
  const toggleLineSi = (next: boolean): void => {
    if (!editLine) return;
    updateLineMutation.mutate(
      { id: editLine.id, si_enabled: next },
      {
        onSuccess: (updated) => {
          const fresh = updated.lines.find((l) => l.id === editLine.id);
          if (fresh) setEditLine(fresh);
        },
        onError: fail,
      },
    );
  };

  const recalculate = (): void => {
    if (!period) return;
    recalcMutation.mutate(period.id, {
      onSuccess: () => toastSuccess(t.payroll.recalculated),
      onError: fail,
    });
  };

  const approve = (): void => {
    if (!period) return;
    approveMutation.mutate(period.id, {
      onSuccess: () => {
        toastSuccess(t.payroll.approved);
        setApproveOpen(false);
      },
      onError: fail,
    });
  };

  /** Ноорог тооцоог цуцалж, өмнөх сар руу шилжинэ. */
  const cancelDraft = (): void => {
    if (!period) return;
    const label = period.label;
    cancelMutation.mutate(period.id, {
      onSuccess: () => {
        setCancelOpen(false);
        setPeriodId(periods.find((p) => p.id !== period.id)?.id ?? null);
        toastSuccess(`${label} — ${t.payroll.cancelled}`);
      },
      onError: fail,
    });
  };

  const pay = (target: string): void => {
    if (!period) return;
    payMutation.mutate(
      { id: period.id, target, paid_from: "bank" },
      {
        onSuccess: () => {
          toastSuccess(t.payroll.paid);
          setPayTarget(null);
        },
        onError: fail,
      },
    );
  };

  const payables = period
    ? [
        { target: "salary", label: t.payroll.paySalary, owed: period.owed_salary },
        { target: "pit", label: t.payroll.payPit, owed: period.owed_pit },
        { target: "social", label: t.payroll.paySocial, owed: period.owed_social },
      ]
    : [];
  const nextPayable = payables.find((p) => p.owed !== "0.00");

  return (
    <div className="flex flex-col gap-5">
      {/* 1. Толгой + сарын сонголт */}
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ink">{t.payroll.title}</h1>
            <p className="text-sm text-ink-soft">{t.payroll.subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="lg" variant="ghost" icon={<SlidersHorizontal />} onClick={openRates}>
              {t.payroll.rateSettings}
            </Button>
            <Button size="lg" variant="secondary" icon={<Plus />} onClick={() => setNewOpen(true)}>
              {t.payroll.newMonth}
            </Button>
          </div>
        </div>

        {periods.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            {periods.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPeriodId(p.id)}
                className={`flex min-h-12 items-center gap-2 rounded-xl border-2 px-4 text-sm font-semibold transition ${
                  p.id === periodId
                    ? "border-action bg-action-soft text-action-dark"
                    : "border-line bg-surface text-ink-soft hover:bg-surface-sunken"
                }`}
              >
                {p.label}
                <StatusBadge
                  size="sm"
                  tone={STATUS_TONE[p.status] ?? "neutral"}
                  label={
                    t.payroll.status[p.status as keyof typeof t.payroll.status] ?? p.status
                  }
                />
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {period ? (
        <>
          {/* 2. Гурван том тоо */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatBox
              label={t.payroll.grossTotal}
              value={formatMNT(period.gross_total)}
              icon={<Coins />}
              size="lg"
            />
            <StatBox
              label={t.payroll.netTotal}
              value={formatMNT(period.net_total)}
              tone="success"
              icon={<Wallet />}
              size="lg"
              hint={`${period.employee_count} ${t.payroll.employeeSuffix}`}
            />
            <StatBox
              label={t.payroll.employerCost}
              value={formatMNT(period.employer_cost)}
              tone="warning"
              size="lg"
              hint={`${t.payroll.employerSi}: ${formatMNT(period.si_employer_total)}`}
            />
          </div>

          {/* 3. Дараагийн алхам — яг одоо юу хийхийг нэг мөрөөр */}
          {isDraft ? (
            <Card className="flex flex-wrap items-center justify-between gap-4 border-2 border-action/30 bg-action-soft/40 p-5">
              <div>
                <div className="text-base font-bold text-ink">{t.payroll.stepReviewTitle}</div>
                <div className="text-sm text-ink-soft">{t.payroll.stepReviewHint}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="lg"
                  variant="secondary"
                  icon={<RefreshCw />}
                  loading={recalcMutation.isPending}
                  onClick={recalculate}
                >
                  {t.payroll.recalculate}
                </Button>
                <Button size="lg" icon={<CheckCircle2 />} onClick={() => setApproveOpen(true)}>
                  {t.payroll.approve}
                </Button>
                <Button
                  size="lg"
                  variant="ghost"
                  icon={<Trash2 />}
                  loading={cancelMutation.isPending}
                  onClick={() => setCancelOpen(true)}
                >
                  {t.payroll.cancelDraft}
                </Button>
              </div>
            </Card>
          ) : nextPayable ? (
            <Card className="flex flex-wrap items-center justify-between gap-4 border-2 border-warning/30 bg-warning-soft/40 p-5">
              <div>
                <div className="text-base font-bold text-ink">{t.payroll.stepPayTitle}</div>
                <div className="text-sm text-ink-soft">
                  {nextPayable.label} · {formatMNT(nextPayable.owed)}
                </div>
              </div>
              <Button
                size="lg"
                icon={<Wallet />}
                onClick={() => setPayTarget(nextPayable.target)}
              >
                {t.payroll.pay}
              </Button>
            </Card>
          ) : isPaid ? (
            <Card className="flex items-center gap-3 border-2 border-success/30 bg-success-soft/40 p-5">
              <CheckCircle2 className="h-6 w-6 text-success-dark" />
              <div className="text-base font-bold text-ink">{t.payroll.stepDone}</div>
            </Card>
          ) : null}

          {/* Өглөгийн задаргаа — батлагдсаны дараа */}
          {!isDraft ? (
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-soft">
                {t.payroll.payables}
              </h2>
              <div className="flex flex-col gap-2">
                {payables.map((row) => {
                  const settled = row.owed === "0.00";
                  return (
                    <div
                      key={row.target}
                      className="flex items-center justify-between gap-3 rounded-xl bg-surface-sunken px-4 py-3"
                    >
                      <span className="text-sm text-ink">{row.label}</span>
                      <div className="flex items-center gap-3">
                        <span
                          className={`num font-bold ${settled ? "text-ink-soft" : "text-ink"}`}
                        >
                          {settled ? t.payroll.settled : formatMNT(row.owed)}
                        </span>
                        {!settled ? (
                          <Button size="md" onClick={() => setPayTarget(row.target)}>
                            {t.payroll.pay}
                          </Button>
                        ) : (
                          <CheckCircle2 className="h-5 w-5 text-success" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          ) : null}

          {/* 4. Ажилтны жагсаалт — энгийн 4 багана */}
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
                {t.payroll.employees} ({period.employee_count})
              </h2>
              <button
                type="button"
                onClick={() => setShowRates((v) => !v)}
                aria-expanded={showRates}
                className="flex h-11 items-center gap-1.5 rounded-lg px-3 text-[13px] font-medium text-ink-soft transition hover:bg-surface-sunken hover:text-ink"
              >
                <Info className="h-4 w-4" />
                {t.payroll.rates}
                <ChevronDown className={`h-4 w-4 transition ${showRates ? "rotate-180" : ""}`} />
              </button>
            </div>

            {showRates ? (
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 border-b border-line bg-surface-sunken px-4 py-3 text-xs sm:grid-cols-4">
                <span className="text-ink-soft">
                  {t.payroll.siEmployeeRate}:{" "}
                  <b className="num text-ink">
                    {(Number(period.si_employee_rate) * 100).toFixed(1)}%
                  </b>
                </span>
                <span className="text-ink-soft">
                  {t.payroll.siEmployerRate}:{" "}
                  <b className="num text-ink">
                    {(Number(period.si_employer_rate) * 100).toFixed(1)}%
                  </b>
                </span>
                <span className="text-ink-soft">
                  {t.payroll.pitRate}:{" "}
                  <b className="num text-ink">{(Number(period.pit_rate) * 100).toFixed(1)}%</b>
                </span>
                <span className="text-ink-soft">
                  {t.payroll.pitCredit}:{" "}
                  <b className="num text-ink">{formatMNT(period.pit_credit)}</b>
                </span>
              </div>
            ) : null}

            <div className="divide-y divide-line">
              {period.lines.map((line) => {
                const deductions =
                  Number(line.si_employee) + Number(line.pit) + Number(line.advance) +
                  Number(line.other_deduction);
                return (
                  <button
                    key={line.id}
                    type="button"
                    disabled={!isDraft}
                    onClick={() => isDraft && setEditLine(line)}
                    className={`flex w-full items-center gap-4 px-4 py-3 text-left transition ${
                      isDraft ? "hover:bg-surface-sunken" : "cursor-default"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-semibold text-ink">{line.employee_name}</div>
                      <div className="truncate text-xs text-ink-soft">
                        {line.position ?? "—"} ·{" "}
                        <span className={line.partial_month ? "font-semibold text-warning-dark" : ""}>
                          {formatNumber(line.worked_days)}/{formatNumber(line.month_days)}{" "}
                          {t.payroll.daysShort}
                        </span>
                        {/* Сарын дундуур ажилд орсон/гарсан бол хугацааг нь заана */}
                        {line.partial_month && line.worked_from && line.worked_to ? (
                          <span className="ml-1 text-warning-dark">
                            ({formatDate(line.worked_from)}–{formatDate(line.worked_to)})
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="hidden text-right sm:block">
                      <div className="num text-sm text-ink">{formatMNT(line.gross)}</div>
                      <div className="flex items-center gap-2 text-xs text-ink-soft">{t.payroll.gross}</div>
                    </div>
                    <div className="hidden text-right sm:block">
                      <div className="num text-sm text-danger-dark">
                        −{formatMNT(String(deductions))}
                      </div>
                      <div className="text-xs text-ink-soft">{t.payroll.deductions}</div>
                    </div>
                    <div className="text-right">
                      <div className="num text-lg font-bold text-success-dark">
                        {formatMNT(line.net)}
                      </div>
                      <div className="text-xs text-ink-soft">{t.payroll.net}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </Card>
        </>
      ) : (
        <Card className="flex flex-col items-center gap-3 p-10 text-center">
          <Coins className="h-10 w-10 text-ink-soft" />
          <div className="text-base font-semibold text-ink">{t.payroll.emptyTitle}</div>
          <p className="max-w-md text-sm text-ink-soft">{t.payroll.emptyHint}</p>
          <Button size="lg" icon={<Plus />} onClick={() => setNewOpen(true)}>
            {t.payroll.newMonth}
          </Button>
        </Card>
      )}

      {/* Шинэ сар үүсгэх */}
      <Modal open={newOpen} onClose={() => setNewOpen(false)} title={t.payroll.newMonth} size="md">
        <div className="flex flex-col gap-4">
          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.payroll.year}
            </div>
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="lg" onClick={() => setNewYear((y) => y - 1)}>
                −
              </Button>
              <span className="num flex-1 text-center text-2xl font-bold">{newYear}</span>
              <Button variant="ghost" size="lg" onClick={() => setNewYear((y) => y + 1)}>
                +
              </Button>
            </div>
          </div>

          <TouchSelect
            label={t.payroll.month}
            value={newMonth}
            onChange={setNewMonth}
            options={MONTHS.map((label, i) => ({ value: i + 1, label }))}
            columns={3}
          />

          {/* Ажилтныг гараар сонгоно — хоосон бол бүгд орно */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                {t.payroll.selectEmployees}
              </span>
              <span className="text-xs text-ink-soft">
                {pickedEmployees.length > 0
                  ? `${pickedEmployees.length} ${t.payroll.selectedCount}`
                  : t.common.all}
              </span>
            </div>
            <div className="scroll-touch flex max-h-56 flex-col gap-1.5 overflow-y-auto rounded-xl border border-line p-2">
              {employees.map((employee) => {
                const checked = pickedEmployees.includes(employee.id);
                return (
                  <button
                    key={employee.id}
                    type="button"
                    onClick={() =>
                      setPickedEmployees((prev) =>
                        checked ? prev.filter((id) => id !== employee.id) : [...prev, employee.id],
                      )
                    }
                    className={[
                      "flex min-h-12 items-center gap-3 rounded-lg border px-3 text-left transition-colors",
                      checked
                        ? "border-action bg-action-soft/50"
                        : "border-transparent hover:bg-surface-alt",
                    ].join(" ")}
                  >
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded border-2 ${
                        checked ? "border-action bg-action text-white" : "border-line-strong"
                      }`}
                    >
                      {checked ? <Check className="h-4 w-4" /> : null}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-[15px] font-semibold text-ink">
                        {employee.full_name}
                      </span>
                      <span className="num truncate text-xs text-ink-soft">
                        {employee.position ?? "—"} · {formatMNT(employee.base_salary)}
                        {employee.si_enabled ? "" : ` · ${t.payroll.siDisabled}`}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            {pickedEmployees.length > 0 ? (
              <button
                type="button"
                onClick={() => setPickedEmployees([])}
                className="self-start rounded-lg px-2 py-1 text-xs font-medium text-ink-soft hover:text-ink"
              >
                {t.common.clear}
              </button>
            ) : null}
          </div>

          <p className="rounded-xl bg-info-soft px-4 py-3 text-sm text-info-dark">
            {pickedEmployees.length > 0 ? t.payroll.selectEmployeesHint : t.payroll.newMonthHint}
          </p>

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setNewOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              loading={createMutation.isPending}
              onClick={createPeriod}
            >
              {t.payroll.calculate}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Мөр засах */}
      <Modal
        open={Boolean(editLine)}
        onClose={() => setEditLine(null)}
        title={editLine?.employee_name ?? ""}
        size="md"
      >
        {editLine ? (
          <div className="flex flex-col gap-3">
            {EDIT_FIELDS.map((f) => {
              const raw = String(editLine[f.key as keyof PayrollLine] ?? "0");
              return (
                <button
                  key={f.key}
                  type="button"
                  onClick={() =>
                    openNumPad({
                      target: f.key,
                      title: f.label,
                      value: raw,
                      allowDecimal: true,
                      suffix: f.money ? t.units.mnt : "",
                    })
                  }
                  className="flex min-h-16 items-center justify-between rounded-xl border-2 border-line bg-surface-alt px-5"
                >
                  <span className="text-sm text-ink-soft">{f.label}</span>
                  <span className="num text-xl font-bold text-ink">
                    {f.money ? formatMNT(raw) : formatNumber(raw)}
                  </span>
                </button>
              );
            })}

            {/* НДШ бодох эсэх — унтраавал НДШ 0, ХХОАТ нийт цалингаас */}
            <button
              type="button"
              onClick={() => toggleLineSi(!editLine.si_enabled)}
              disabled={!isDraft || updateLineMutation.isPending}
              aria-pressed={editLine.si_enabled}
              className="flex min-h-16 items-center justify-between gap-4 rounded-xl border-2 border-line bg-surface-alt px-5 text-left disabled:opacity-60"
            >
              <span className="flex min-w-0 flex-col">
                <span className="text-sm text-ink-soft">{t.payroll.siEnabled}</span>
                <span className="truncate text-xs text-ink-faint">{t.payroll.siHint}</span>
              </span>
              <span
                className={`flex h-8 w-14 shrink-0 items-center rounded-full p-1 transition-colors ${
                  editLine.si_enabled ? "bg-success" : "bg-surface-sunken"
                }`}
              >
                <span
                  className={`h-6 w-6 rounded-full bg-white shadow transition-transform ${
                    editLine.si_enabled ? "translate-x-6" : "translate-x-0"
                  }`}
                />
              </span>
            </button>

            {editLine.partial_month && editLine.worked_from && editLine.worked_to ? (
              <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning-dark">
                {t.payroll.partialMonth}: {formatDate(editLine.worked_from)} —{" "}
                {formatDate(editLine.worked_to)} ({formatNumber(editLine.worked_days)}/
                {formatNumber(editLine.month_days)} {t.payroll.daysShort})
              </p>
            ) : null}

            <div className="rounded-xl bg-surface-sunken p-4 text-sm">
              <div className="flex justify-between">
                <span>{t.payroll.earnedSalary}</span>
                <span className="num">{formatMNT(editLine.earned_salary)}</span>
              </div>
              <div className="flex justify-between">
                <span>{t.payroll.gross}</span>
                <b className="num">{formatMNT(editLine.gross)}</b>
              </div>
              <div className="flex justify-between text-ink-soft">
                <span>
                  − {t.payroll.socialInsurance}
                  {editLine.si_enabled ? "" : ` (${t.payroll.siDisabled})`}
                </span>
                <span className="num">{formatMNT(editLine.si_employee)}</span>
              </div>
              <div className="flex justify-between text-ink-soft">
                <span>
                  − {t.payroll.incomeTax}
                  {editLine.si_enabled ? "" : ` (${t.payroll.siDisabled})`}
                </span>
                <span className="num">{formatMNT(editLine.pit)}</span>
              </div>
              {editLine.advance !== "0.00" ? (
                <div className="flex justify-between text-ink-soft">
                  <span>− {t.payroll.advance}</span>
                  <span className="num">{formatMNT(editLine.advance)}</span>
                </div>
              ) : null}
              <div className="mt-2 flex justify-between border-t border-line pt-2 text-base font-bold">
                <span>{t.payroll.net}</span>
                <span className="num text-success-dark">{formatMNT(editLine.net)}</span>
              </div>
            </div>

            <Button size="lg" onClick={() => setEditLine(null)}>
              {t.common.close}
            </Button>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={approveOpen}
        title={t.payroll.approve}
        message={t.payroll.approveWarning}
        confirmLabel={t.payroll.approve}
        loading={approveMutation.isPending}
        onConfirm={approve}
        onCancel={() => setApproveOpen(false)}
      />

      <ConfirmDialog
        open={cancelOpen}
        variant="danger"
        title={t.payroll.cancelDraft}
        message={t.payroll.cancelWarning}
        confirmLabel={t.payroll.cancelDraft}
        loading={cancelMutation.isPending}
        onConfirm={cancelDraft}
        onCancel={() => setCancelOpen(false)}
      />

      <ConfirmDialog
        open={Boolean(payTarget)}
        title={t.payroll.pay}
        message={t.payroll.payWarning}
        confirmLabel={t.payroll.pay}
        loading={payMutation.isPending}
        onConfirm={() => payTarget && pay(payTarget)}
        onCancel={() => setPayTarget(null)}
      />

      {/* Цалингийн хувь хэмжээ — хууль өөрчлөгдвөл эндээс */}
      <Modal
        open={ratesOpen}
        onClose={() => setRatesOpen(false)}
        size="md"
        title={t.payroll.rateSettings}
        subtitle={t.payroll.rateSettingsHint}
      >
        <div className="flex flex-col gap-4">
          {RATE_FIELDS.map((field) => (
            <TextField
              key={field.key}
              label={field.label}
              value={rateDraft[field.key] ?? ""}
              onChange={(value) => setRateDraft((prev) => ({ ...prev, [field.key]: value }))}
              hint={field.pct ? t.units.percent : t.units.mnt}
            />
          ))}
          <p className="rounded-xl bg-info-soft px-4 py-3 text-sm text-info-dark">
            {t.payroll.rateSettingsHint}
          </p>
          {rateError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {rateError}
            </p>
          ) : null}
          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setRatesOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              loading={updateSetting.isPending}
              onClick={() => void saveRates()}
            >
              {t.common.save}
            </Button>
          </div>
        </div>
      </Modal>

      <NumPadModal onSubmit={(target, value) => saveField(target, value || "0")} />
    </div>
  );
}

export default PayrollPage;
