import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Database, Droplets, SlidersHorizontal, TriangleAlert } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useAdjustTankMutation, useTanks } from "../../api/queries/tanks";
import type { Tank } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import type { Tone } from "../../lib/constants";
import { dNeg, dSub, dSum, dToNumber } from "../../lib/decimal";
import { formatLiters, formatMNT } from "../../lib/format";
import { useCan } from "../../hooks/usePermission";
import { ChipGroup, NumberField, TextAreaField } from "../catalog/_shared";

/** Дүүргэлтийн хувиас хамаарсан өнгө: >50% ногоон, 20–50% шар, <20% улаан. */
function levelTone(pct: number): Tone {
  if (pct > 50) return "success";
  if (pct >= 20) return "warning";
  return "danger";
}

type AdjustSign = "add" | "sub";

export function TanksPage() {
  const navigate = useNavigate();
  const canManage = useCan("tanks.manage");

  const tanksQuery = useTanks({ active_only: false });
  const adjustMutation = useAdjustTankMutation();

  const [adjustTank, setAdjustTank] = useState<Tank | null>(null);
  const [sign, setSign] = useState<AdjustSign>("add");
  const [liters, setLiters] = useState("");
  const [note, setNote] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tanks = useMemo(() => tanksQuery.data?.items ?? [], [tanksQuery.data]);

  const totals = useMemo(() => {
    const capacity = dSum(tanks.map((tank) => tank.capacity_l));
    const current = dSum(tanks.map((tank) => tank.current_l));
    const value = dSum(tanks.map((tank) => tank.stock_value));
    const low = tanks.filter((tank) => tank.is_low).length;
    return { capacity, current, value, low };
  }, [tanks]);

  const openAdjust = (tank: Tank): void => {
    setAdjustTank(tank);
    setSign("add");
    setLiters("");
    setNote("");
    setError(null);
  };

  const closeAdjust = (): void => {
    setAdjustTank(null);
    setConfirmOpen(false);
  };

  const signedLiters = sign === "sub" ? dNeg(liters) : liters;

  const submitAdjust = (): void => {
    if (!adjustTank) return;
    setError(null);
    adjustMutation.mutate(
      { id: adjustTank.id, payload: { liters: signedLiters, note: note.trim() || null } },
      {
        onSuccess: () => closeAdjust(),
        onError: (mutationError) => {
          setConfirmOpen(false);
          setError(errorMessage(mutationError));
        },
      },
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.tanks.title}
        subtitle={t.tanks.movements}
        actions={
          <Button variant="secondary" size="md" onClick={() => tanksQuery.refetch()}>
            {t.common.refresh}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox label={t.tanks.capacity} value={formatLiters(totals.capacity, 0)} tone="neutral" />
        <StatBox label={t.tanks.current} value={formatLiters(totals.current, 0)} tone="action" />
        <StatBox label={t.tanks.stockValue} value={formatMNT(totals.value)} tone="success" />
        <StatBox
          label={t.tanks.low}
          value={totals.low}
          tone={totals.low > 0 ? "danger" : "neutral"}
          icon={totals.low > 0 ? <TriangleAlert className="h-5 w-5" /> : undefined}
        />
      </div>

      {tanksQuery.isLoading ? (
        <div className="flex items-center justify-center py-20 text-ink-soft">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : tanks.length === 0 ? (
        <EmptyState icon={<Database className="h-7 w-7" />} title={t.common.empty} hint={t.common.emptyHint} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {tanks.map((tank) => {
            const pct = dToNumber(tank.fill_pct);
            const available = dSub(tank.capacity_l, tank.current_l);
            const minPct =
              dToNumber(tank.capacity_l) > 0
                ? (dToNumber(tank.min_level_l) / dToNumber(tank.capacity_l)) * 100
                : 0;

            return (
              <section
                key={tank.id}
                className="flex flex-col gap-4 rounded-xl border border-line bg-white p-5"
              >
                <div className="flex items-start gap-3">
                  <span
                    className="mt-1 h-10 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: tank.fuel.color_hex }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-lg font-bold text-ink">{tank.name}</h3>
                    <p className="truncate text-sm text-ink-soft">
                      {tank.fuel.name_mn} · {tank.fuel.code}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    {tank.is_low ? <StatusBadge label={t.tanks.low} tone="danger" dot size="sm" /> : null}
                    {!tank.is_active ? (
                      <StatusBadge label={t.common.inactive} tone="neutral" size="sm" />
                    ) : null}
                  </div>
                </div>

                <div className="flex items-end justify-between gap-3">
                  <span className="num text-[40px] leading-none font-bold text-ink">
                    {formatLiters(tank.current_l, 0)}
                  </span>
                  <span className="num text-2xl font-bold" style={{ color: tank.fuel.color_hex }}>
                    {pct.toFixed(0)}
                    {t.units.percent}
                  </span>
                </div>

                <ProgressBar
                  value={pct}
                  tone={levelTone(pct)}
                  size="lg"
                  markerPct={minPct}
                  label={t.tanks.fillPct}
                  valueLabel={`${formatLiters(tank.current_l)} / ${formatLiters(tank.capacity_l, 0)}`}
                />

                <dl className="grid grid-cols-3 gap-3 border-t border-line pt-3">
                  <div>
                    <dt className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
                      {t.tanks.capacity}
                    </dt>
                    <dd className="num text-[15px] font-semibold text-ink">
                      {formatLiters(tank.capacity_l, 0)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
                      {t.common.balance}
                    </dt>
                    <dd className="num text-[15px] font-semibold text-ink">{formatLiters(available, 0)}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
                      {t.tanks.avgCost}
                    </dt>
                    <dd className="num text-[15px] font-semibold text-ink">{formatMNT(tank.avg_cost)}</dd>
                  </div>
                </dl>

                <div className="flex flex-wrap gap-2.5">
                  <Button
                    variant="secondary"
                    size="md"
                    icon={<Droplets />}
                    onClick={() => navigate(`/tanks/${tank.id}`)}
                  >
                    {t.tanks.movements}
                  </Button>
                  {canManage ? (
                    <Button
                      variant="primary"
                      size="md"
                      icon={<SlidersHorizontal />}
                      onClick={() => openAdjust(tank)}
                    >
                      {t.tanks.adjust}
                    </Button>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <Modal
        open={adjustTank !== null}
        onClose={closeAdjust}
        size="md"
        title={t.tanks.adjust}
        subtitle={adjustTank?.name}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={closeAdjust}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={liters === "" || dToNumber(liters) === 0}
              onClick={() => setConfirmOpen(true)}
            >
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <ChipGroup<AdjustSign>
            label={t.tanks.movementType}
            value={sign}
            onChange={setSign}
            options={[
              { value: "add", label: "+ Нэмэгдэл" },
              { value: "sub", label: "− Хорогдол" },
            ]}
          />
          <NumberField
            name="tank-adjust-liters"
            label={t.procurement.liters}
            value={liters}
            onChange={setLiters}
            suffix={t.units.liter}
            maxDecimals={3}
            hint={t.tanks.adjustHint}
          />
          <TextAreaField label={t.common.note} value={note} onChange={setNote} />

          {adjustTank ? (
            <div className="rounded-xl border border-line bg-surface-alt px-4 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm text-ink-soft">{t.tanks.balanceAfter}</span>
                <span className="num text-xl font-bold text-ink">
                  {formatLiters(dSum([adjustTank.current_l, signedLiters]))}
                </span>
              </div>
            </div>
          ) : null}

          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmOpen}
        title={t.tanks.adjust}
        message={t.tanks.adjustConfirm}
        variant="warning"
        loading={adjustMutation.isPending}
        onConfirm={submitAdjust}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

export default TanksPage;
