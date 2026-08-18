import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Banknote, Check, ChevronLeft, ChevronRight, Database, Gauge } from "lucide-react";

import { errorMessage } from "../../api/client";
import { usePumps } from "../../api/queries/pumps";
import { useCloseShiftMutation, useCurrentShift, useOpenShiftMutation } from "../../api/queries/shifts";
import { useSettings } from "../../api/queries/system";
import { useTanks } from "../../api/queries/tanks";
import type {
  LitersStr,
  MoneyStr,
  ShiftCloseRequest,
  ShiftOpenRequest,
  TankDipInput,
  TotalizerReadingInput,
  UUID,
} from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { usePermission } from "../../hooks/usePermission";
import { usePosEnabled } from "../../hooks/usePosEnabled";
import { t } from "../../i18n/mn";
import { QUICK_CASH } from "../../lib/constants";
import { dCmp, dSub, toDisplay } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { AttendantShiftPage } from "./AttendantShiftPage";

type StepKey = 0 | 1 | 2;

const PAD_CASH = "shift.cash";
const PAD_DIP = "shift.dip:";
const PAD_READING = "shift.reading:";

interface StepMeta {
  key: StepKey;
  label: string;
  icon: typeof Banknote;
}

/**
 * Литрийн утгыг байгаагаар нь (3 орон) хадгална.
 * `toDisplay` 2 орон руу дугуйлдаг тул хэмжилтэд ашиглаж болохгүй.
 */
function litersOf(value: string | null | undefined): LitersStr {
  const raw = (value ?? "").trim();
  return raw === "" ? "0" : raw;
}

/**
 * Урьдчилсан зөрүү (2 орны нарийвчлалтай) — эцсийн тооцоог сервер хийнэ.
 */
function variance(actual: string, book: string): string {
  return dSub(actual, book);
}

export function ShiftPage() {
  // ПОС унтраалттай бол ээлж түгээгчийн өдрийн горимоор явна.
  const { enabled: posEnabled } = usePosEnabled();
  if (!posEnabled) return <AttendantShiftPage />;
  return <PosShiftPage />;
}

function PosShiftPage() {
  const navigate = useNavigate();
  const { can } = usePermission();

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: tanksPage, isLoading: tanksLoading } = useTanks({ active_only: true });
  const { data: pumpsPage, isLoading: pumpsLoading } = usePumps({ active_only: true });
  const { data: settings, isLoading: settingsLoading } = useSettings();

  /** Тоолуурын заалт бүртгэх эсэх — эзний тохиргоо (анхдагч: идэвхтэй). */
  const totalizerOn =
    settings === undefined
      ? true
      : settings.shift_totalizer_enabled === true || settings.shift_totalizer_enabled === "true";

  const openMutation = useOpenShiftMutation();
  const closeMutation = useCloseShiftMutation();

  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const shift = current?.shift ?? null;
  const mode: "open" | "close" = shift ? "close" : "open";

  const tanks = useMemo(() => tanksPage?.items ?? [], [tanksPage]);
  const nozzles = useMemo(
    () =>
      (pumpsPage?.items ?? []).flatMap((pump) =>
        pump.nozzles.map((nozzle) => ({ pump, nozzle })),
      ),
    [pumpsPage],
  );

  const [step, setStep] = useState<StepKey>(0);
  const [cash, setCash] = useState<MoneyStr>("0.00");
  const [dips, setDips] = useState<Record<UUID, LitersStr>>({});
  const [readings, setReadings] = useState<Record<UUID, LitersStr>>({});
  const [error, setError] = useState<string | null>(null);

  // Тоолуурын анхны утга — хадгалагдсан заалт.
  useEffect(() => {
    if (nozzles.length === 0) return;
    setReadings((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const { nozzle } of nozzles) {
        if (next[nozzle.id] === undefined) {
          next[nozzle.id] = litersOf(nozzle.totalizer);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [nozzles]);

  // Савны анхны утга — дансны үлдэгдэл (түгээгч зөвхөн зөрүүг л засна).
  useEffect(() => {
    if (tanks.length === 0) return;
    setDips((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const tank of tanks) {
        if (next[tank.id] === undefined) {
          next[tank.id] = litersOf(tank.current_l);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [tanks]);

  // Тоолуур унтраалттай бол 3 дахь алхам огт байхгүй.
  const steps: StepMeta[] = [
    { key: 0, label: mode === "open" ? t.shift.openingCash : t.shift.declaredCash, icon: Banknote },
    { key: 1, label: t.shift.tankDips, icon: Database },
    ...(totalizerOn ? [{ key: 2 as StepKey, label: t.shift.totalizers, icon: Gauge }] : []),
  ];
  const lastStep: StepKey = totalizerOn ? 2 : 1;

  // Тохиргоо унтарсан үед сүүлийн алхам дээр зогссон бол буцаана.
  useEffect(() => {
    if (!totalizerOn && step === 2) setStep(1);
  }, [totalizerOn, step]);

  const handleNumPad = (target: string, value: string): void => {
    if (target === PAD_CASH) {
      setCash(toDisplay(value));
      return;
    }
    if (target.startsWith(PAD_DIP)) {
      const id = target.slice(PAD_DIP.length);
      setDips((prev) => ({ ...prev, [id]: litersOf(value) }));
      return;
    }
    if (target.startsWith(PAD_READING)) {
      const id = target.slice(PAD_READING.length);
      setReadings((prev) => ({ ...prev, [id]: litersOf(value) }));
    }
  };

  const tankDips: TankDipInput[] = tanks.map((tank) => ({
    tank_id: tank.id,
    dip_liters: dips[tank.id] ?? litersOf(tank.current_l),
  }));

  const totalizerReadings: TotalizerReadingInput[] = totalizerOn
    ? nozzles.map(({ nozzle }) => ({
        nozzle_id: nozzle.id,
        reading: readings[nozzle.id] ?? litersOf(nozzle.totalizer),
      }))
    : [];

  const allowed = mode === "open" ? can("shifts.open") : can("shifts.close");
  const loading = shiftLoading || tanksLoading || pumpsLoading || settingsLoading;
  const busy = openMutation.isPending || closeMutation.isPending;

  const handleSubmit = (): void => {
    setError(null);

    if (dCmp(cash, "0") < 0) {
      setError(t.errors.validation);
      return;
    }

    if (mode === "open") {
      const payload: ShiftOpenRequest = {
        opening_cash: cash,
        tank_dips: tankDips,
        totalizer_readings: totalizerReadings,
      };
      openMutation.mutate(payload, {
        onSuccess: () => {
          toastSuccess(t.shift.open);
          navigate("/pos");
        },
        onError: (cause) => {
          const message = errorMessage(cause);
          setError(message);
          toastError(message);
        },
      });
      return;
    }

    if (!shift) return;
    const payload: ShiftCloseRequest = {
      declared_cash: cash,
      tank_dips: tankDips,
      totalizer_readings: totalizerReadings,
    };
    closeMutation.mutate(
      { id: shift.id, payload },
      {
        onSuccess: (report) => navigate(`/shift/report/${report.shift.id}`),
        onError: (cause) => {
          const message = errorMessage(cause);
          setError(message);
          toastError(message);
        },
      },
    );
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.shift.title} />
        <div className="rounded-2xl border border-danger bg-danger-soft px-6 py-10 text-center text-danger-dark">
          {t.auth.forbiddenHint}
        </div>
      </div>
    );
  }

  const expected = current?.cash.expected_cash ?? "0.00";
  const cashVariance = mode === "close" ? dSub(cash, expected) : null;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5">
      <PageHeader
        title={mode === "open" ? t.shift.open : t.shift.close}
        subtitle={
          shift ? (
            <span className="num">
              {t.shift.number}
              {shift.number} · {t.shift.opened}: {formatDateTime(shift.opened_at)} ·{" "}
              {formatMNT(current?.sales.gross_total ?? "0")}
            </span>
          ) : (
            t.shift.noOpen
          )
        }
      />

      {/* Алхмууд */}
      <ol className={`grid gap-2 ${totalizerOn ? "grid-cols-3" : "grid-cols-2"}`}>
        {steps.map((meta) => {
          const Icon = meta.icon;
          const active = meta.key === step;
          const done = meta.key < step;
          return (
            <li key={meta.key}>
              <button
                type="button"
                onClick={() => setStep(meta.key)}
                className={[
                  "flex min-h-16 w-full items-center gap-3 rounded-xl border-2 px-3 py-2 text-left transition-colors",
                  active
                    ? "border-action bg-action-soft"
                    : done
                      ? "border-success bg-success-soft"
                      : "border-line-strong bg-white",
                ].join(" ")}
              >
                <span
                  className={`num flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg font-black text-white ${
                    active ? "bg-action" : done ? "bg-success" : "bg-ink-faint"
                  }`}
                >
                  {done ? <Check className="h-5 w-5" /> : meta.key + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold text-ink">{meta.label}</span>
                </span>
                <Icon className="hidden h-5 w-5 shrink-0 text-ink-faint sm:block" />
              </button>
            </li>
          );
        })}
      </ol>

      {/* Алхам 1 — касс */}
      {step === 0 ? (
        <section className="flex flex-col gap-4 rounded-2xl border border-line bg-white px-5 py-5">
          <h2 className="text-lg font-bold text-ink">
            {mode === "open" ? t.shift.openingCash : t.shift.declaredCash}
          </h2>

          <button
            type="button"
            onClick={() =>
              openNumPad({
                target: PAD_CASH,
                title: mode === "open" ? t.shift.openingCash : t.shift.declaredCash,
                value: cash,
                allowDecimal: true,
                suffix: t.units.mnt,
              })
            }
            className="flex min-h-24 w-full items-center justify-between gap-4 rounded-2xl border-2 border-line-strong bg-surface-alt px-6 active:bg-surface-sunken"
          >
            <span className="text-base font-semibold text-ink-soft">{t.common.amount}</span>
            <span className="num text-[56px] leading-none font-black text-ink">{formatMNT(cash)}</span>
          </button>

          {mode === "close" ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-line-strong bg-surface-alt px-4 py-3">
                <div className="text-xs font-semibold text-ink-soft">{t.shift.openingCash}</div>
                <div className="num text-xl font-bold text-ink">
                  {formatMNT(current?.cash.opening_cash ?? "0")}
                </div>
              </div>
              <div className="rounded-xl border border-line-strong bg-surface-alt px-4 py-3">
                <div className="text-xs font-semibold text-ink-soft">{t.shift.expectedCash}</div>
                <div className="num text-xl font-bold text-ink">{formatMNT(expected)}</div>
              </div>
              <div
                className={`rounded-xl border-2 px-4 py-3 ${
                  cashVariance === null || dCmp(cashVariance, "0") === 0
                    ? "border-line-strong bg-surface-alt"
                    : dCmp(cashVariance, "0") > 0
                      ? "border-success bg-success-soft"
                      : "border-danger bg-danger-soft"
                }`}
              >
                <div className="text-xs font-semibold text-ink-soft">{t.shift.overShort}</div>
                <div className="num text-xl font-bold text-ink">{formatMNT(cashVariance)}</div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* Алхам 2 — сав */}
      {step === 1 ? (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-white px-5 py-5">
          <h2 className="text-lg font-bold text-ink">{t.shift.tankDips}</h2>
          <p className="text-sm text-ink-soft">{t.shift.bookLiters}</p>

          <ul className="flex flex-col gap-3">
            {tanks.map((tank) => {
              const dip = dips[tank.id] ?? litersOf(tank.current_l);
              const delta = variance(dip, tank.current_l);
              const zero = dCmp(delta, "0") === 0;
              return (
                <li
                  key={tank.id}
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-line-strong bg-surface-alt px-4 py-3"
                >
                  <span
                    className="h-10 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: tank.fuel.color_hex }}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-base font-bold text-ink">{tank.name}</span>
                    <span className="num block truncate text-sm text-ink-soft">
                      {tank.fuel.name_mn} · {t.shift.bookLiters}: {formatLiters(tank.current_l, 3)}
                    </span>
                  </span>

                  <button
                    type="button"
                    onClick={() =>
                      openNumPad({
                        target: `${PAD_DIP}${tank.id}`,
                        title: `${tank.name} — ${t.shift.dip}`,
                        value: dip,
                        allowDecimal: true,
                        suffix: t.units.liter,
                      })
                    }
                    className="num h-14 min-w-40 rounded-xl border-2 border-line-strong bg-white px-4 text-right text-2xl font-bold text-ink active:bg-surface-sunken"
                  >
                    {formatNumber(dip, 3)}
                  </button>

                  {mode === "close" ? (
                    <span
                      className={`num h-14 min-w-32 rounded-xl border px-3 py-2 text-right text-sm font-bold ${
                        zero
                          ? "border-line-strong bg-white text-ink-soft"
                          : dCmp(delta, "0") > 0
                            ? "border-success bg-success-soft text-success-dark"
                            : "border-danger bg-danger-soft text-danger-dark"
                      }`}
                    >
                      <span className="block text-[11px] font-semibold text-ink-soft">
                        {t.shift.variance}
                      </span>
                      {formatLiters(delta, 2)}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {/* Алхам 3 — тоолуур (зөвхөн тохиргоо идэвхтэй үед) */}
      {step === 2 && totalizerOn ? (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-white px-5 py-5">
          <h2 className="text-lg font-bold text-ink">{t.shift.totalizers}</h2>

          <ul className="flex flex-col gap-3">
            {nozzles.map(({ pump, nozzle }) => {
              const reading = readings[nozzle.id] ?? litersOf(nozzle.totalizer);
              const delta = variance(reading, nozzle.totalizer);
              return (
                <li
                  key={nozzle.id}
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-line-strong bg-surface-alt px-4 py-3"
                >
                  <span
                    className="num flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-base font-black text-white"
                    style={{ backgroundColor: nozzle.color_hex }}
                  >
                    {pump.number}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-base font-bold text-ink">
                      {pump.name} · {t.pumps.nozzleNo}
                      {nozzle.nozzle_number}
                    </span>
                    <span className="num block truncate text-sm text-ink-soft">
                      {nozzle.fuel_name} · {t.pumps.totalizer}: {formatLiters(nozzle.totalizer, 3)}
                    </span>
                  </span>

                  <button
                    type="button"
                    onClick={() =>
                      openNumPad({
                        target: `${PAD_READING}${nozzle.id}`,
                        title: `${pump.name} · ${t.pumps.nozzleNo}${nozzle.nozzle_number}`,
                        value: reading,
                        allowDecimal: true,
                        suffix: t.units.liter,
                      })
                    }
                    className="num h-14 min-w-44 rounded-xl border-2 border-line-strong bg-white px-4 text-right text-2xl font-bold text-ink active:bg-surface-sunken"
                  >
                    {formatNumber(reading, 3)}
                  </button>

                  {mode === "close" ? (
                    <span className="num h-14 min-w-32 rounded-xl border border-line-strong bg-white px-3 py-2 text-right text-sm font-bold text-ink">
                      <span className="block text-[11px] font-semibold text-ink-soft">
                        {t.shift.readingDelta}
                      </span>
                      {formatLiters(delta, 2)}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-danger bg-danger-soft px-4 py-3 text-[15px] font-semibold text-danger-dark">
          {error}
        </div>
      ) : null}

      {/* Хөл */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="secondary"
          size="lg"
          icon={<ChevronLeft />}
          disabled={step === 0 || busy}
          onClick={() => setStep((prev) => (prev > 0 ? ((prev - 1) as StepKey) : prev))}
        >
          {t.common.prev}
        </Button>

        {step < lastStep ? (
          <Button
            variant="primary"
            size="lg"
            iconRight={<ChevronRight />}
            onClick={() => setStep((prev) => (prev < lastStep ? ((prev + 1) as StepKey) : prev))}
            className="min-w-48"
          >
            {t.common.next}
          </Button>
        ) : (
          <Button
            variant={mode === "open" ? "success" : "danger"}
            size="lg"
            loading={busy}
            onClick={handleSubmit}
            className="min-w-56"
          >
            {mode === "open" ? t.shift.open : t.shift.close}
          </Button>
        )}
      </div>

      <NumPadModal
        onSubmit={handleNumPad}
        quickFor={(target) => (target === PAD_CASH ? QUICK_CASH : undefined)}
      />
    </div>
  );
}

export default ShiftPage;
