/**
 * Салбарын эхний үлдэгдэл — НЭГ УДАА (Админ панел → Салбарын тохиргоо).
 *
 * Сав бүрд литр + литрийн өртөг, хошуу бүрд тоолуурын одоогийн заалт. Хадгалмагц
 * `branch.opening_done_at` бөглөгдөж, картан дээр зөвхөн «оруулагдсан» мэдээлэл
 * үлдэнэ — дахин оруулах боломжгүй.
 */
import { useMemo, useState } from "react";
import { CheckCircle2, Lock } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranchOpeningMutation } from "../../api/queries/branches";
import type { Branch, Pump, Tank, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { dMul, dSum } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, todayInput } from "../../lib/format";
import { DateField, NumberField } from "../../pages/catalog/_shared";
import { useUiStore } from "../../stores/ui";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { EmptyState } from "../ui/EmptyState";

interface TankDraft {
  liters: string;
  unit_cost: string;
}

export function BranchOpeningCard({
  branch,
  tanks,
  pumps,
}: {
  branch: Branch;
  tanks: Tank[];
  pumps: Pump[];
}) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const mutation = useBranchOpeningMutation();

  const [asOf, setAsOf] = useState(todayInput());
  const [tankDrafts, setTankDrafts] = useState<Record<UUID, TankDraft>>({});
  const [nozzleDrafts, setNozzleDrafts] = useState<Record<UUID, string>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);

  const nozzles = useMemo(
    () => pumps.flatMap((pump) => pump.nozzles.map((nozzle) => ({ pump, nozzle }))),
    [pumps],
  );
  const activeTanks = useMemo(() => tanks.filter((tank) => tank.is_active), [tanks]);

  const tankDraft = (id: UUID): TankDraft => tankDrafts[id] ?? { liters: "", unit_cost: "" };
  const patchTank = (id: UUID, patch: Partial<TankDraft>): void =>
    setTankDrafts((prev) => ({ ...prev, [id]: { ...tankDraft(id), ...patch } }));

  const fuelValue = useMemo(
    () =>
      dSum(
        activeTanks.map((tank) => {
          const draft = tankDraft(tank.id);
          return dMul(draft.unit_cost || "0", Number(draft.liters) || 0);
        }),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeTanks, tankDrafts],
  );

  const hasAnyInput =
    activeTanks.some((tank) => Number(tankDraft(tank.id).liters) > 0) ||
    nozzles.some(({ nozzle }) => (nozzleDrafts[nozzle.id] ?? "").trim() !== "");

  const submit = (): void => {
    mutation.mutate(
      {
        id: branch.id,
        as_of: asOf || null,
        tanks: activeTanks
          .filter((tank) => Number(tankDraft(tank.id).liters) > 0)
          .map((tank) => ({
            tank_id: tank.id,
            liters: tankDraft(tank.id).liters,
            unit_cost: tankDraft(tank.id).unit_cost || "0",
          })),
        nozzles: nozzles
          .filter(({ nozzle }) => (nozzleDrafts[nozzle.id] ?? "").trim() !== "")
          .map(({ nozzle }) => ({ nozzle_id: nozzle.id, totalizer: nozzleDrafts[nozzle.id] })),
      },
      {
        onSuccess: () => {
          setConfirmOpen(false);
          toastSuccess(t.branches.openingSaved);
        },
        onError: (error) => {
          setConfirmOpen(false);
          toastError(errorMessage(error));
        },
      },
    );
  };

  if (branch.opening_done_at) {
    return (
      <Card title={t.branches.openingTitle}>
        <div className="flex items-start gap-3 rounded-xl border border-success bg-success-soft px-4 py-3">
          <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-success-dark" />
          <div className="flex flex-col gap-1">
            <span className="font-bold text-success-dark">{t.branches.openingDone}</span>
            <span className="num text-sm text-ink">
              {formatDateTime(branch.opening_done_at)}
              {branch.opening_done_by_name ? ` · ${branch.opening_done_by_name}` : ""}
            </span>
            <span className="text-xs text-ink-soft">{t.branches.openingDoneHint}</span>
          </div>
        </div>
      </Card>
    );
  }

  if (activeTanks.length === 0 && nozzles.length === 0) {
    return (
      <Card title={t.branches.openingTitle}>
        <EmptyState icon={<Lock className="h-7 w-7" />} title={t.branches.openingEmpty} hint={t.branches.openingHint} />
      </Card>
    );
  }

  return (
    <Card title={t.branches.openingTitle} subtitle={t.branches.openingHint}>
      <div className="flex flex-col gap-6">
        <DateField label={t.branches.openingAsOf} value={asOf} onChange={setAsOf} max={todayInput()} />

        {/* --- Сав --- */}
        {activeTanks.length > 0 ? (
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-bold tracking-wide text-ink-soft uppercase">{t.branches.openingTanks}</h3>
            {activeTanks.map((tank) => {
              const hasStock = Number(tank.current_l) > 0;
              const draft = tankDraft(tank.id);
              return (
                <div key={tank.id} className="grid items-end gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3 sm:grid-cols-[1.2fr_1fr_1fr]">
                  <div className="flex flex-col">
                    <span className="font-bold text-ink">{tank.name}</span>
                    <span className="text-xs text-ink-soft">
                      {tank.fuel?.name_mn ?? "—"} · {formatLiters(tank.capacity_l, 0)}
                      {hasStock ? ` · ${formatLiters(tank.current_l, 1)}` : ""}
                    </span>
                    {hasStock ? (
                      <span className="text-xs font-semibold text-warning-dark">{t.branches.openingTankHasStock}</span>
                    ) : null}
                  </div>
                  <NumberField
                    name={`open-l-${tank.id}`}
                    label={t.branches.openingLiters}
                    value={draft.liters}
                    onChange={(value) => patchTank(tank.id, { liters: value })}
                    suffix="л"
                    maxDecimals={3}
                    disabled={hasStock}
                  />
                  <NumberField
                    name={`open-c-${tank.id}`}
                    label={t.branches.openingUnitCost}
                    value={draft.unit_cost}
                    onChange={(value) => patchTank(tank.id, { unit_cost: value })}
                    suffix="₮"
                    maxDecimals={2}
                    disabled={hasStock}
                  />
                </div>
              );
            })}
            <div className="num flex items-baseline justify-between rounded-xl bg-surface-sunken px-4 py-2 text-sm">
              <span className="text-ink-soft">{t.branches.openingFuelValue}</span>
              <span className="font-bold text-ink">{formatMNT(fuelValue)}</span>
            </div>
          </section>
        ) : null}

        {/* --- Хошуу --- */}
        {nozzles.length > 0 ? (
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-bold tracking-wide text-ink-soft uppercase">{t.branches.openingNozzles}</h3>
            {nozzles.map(({ pump, nozzle }) => (
              <div key={nozzle.id} className="grid items-end gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3 sm:grid-cols-[1.2fr_1fr]">
                <div className="flex flex-col">
                  <span className="font-bold text-ink">
                    {pump.name} · №{nozzle.nozzle_number} {nozzle.fuel_name}
                  </span>
                  <span className="num text-xs text-ink-soft">{formatLiters(nozzle.totalizer, 3)}</span>
                </div>
                <NumberField
                  name={`open-n-${nozzle.id}`}
                  label={t.branches.openingTotalizer}
                  value={nozzleDrafts[nozzle.id] ?? ""}
                  onChange={(value) => setNozzleDrafts((prev) => ({ ...prev, [nozzle.id]: value }))}
                  maxDecimals={3}
                />
              </div>
            ))}
          </section>
        ) : null}

        <div className="flex justify-end">
          <Button variant="primary" size="lg" icon={<Lock />} disabled={!hasAnyInput} onClick={() => setConfirmOpen(true)}>
            {t.branches.openingSave}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={t.branches.openingConfirmTitle}
        message={t.branches.openingConfirmText}
        confirmLabel={t.branches.openingSave}
        variant="warning"
        loading={mutation.isPending}
        onConfirm={submit}
        onCancel={() => setConfirmOpen(false)}
      />
    </Card>
  );
}
