import type { ReactNode } from "react";
import { Fuel } from "lucide-react";

import type { Pump, PumpTelemetry, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { EmptyState } from "../ui/EmptyState";
import { Spinner } from "../ui/Spinner";
import { PumpCard } from "./PumpCard";

export interface PumpGridProps {
  pumps: readonly Pump[];
  /** `pump_id` → WebSocket телеметр. */
  telemetry: Record<UUID, PumpTelemetry>;
  onSelect: (pump: Pump) => void;
  loading?: boolean;
  disabled?: boolean;
  /** Насосны дараа нэмэгдэх нэмэлт плитка (жишээ нь «Грам бүтээгдэхүүн»). */
  extra?: ReactNode;
}

/** Талбайн бүх насос — 1/2/3/4 багана дэлгэцийн өргөнөөс хамаарна. */
export function PumpGrid({
  pumps,
  telemetry,
  onSelect,
  loading = false,
  disabled = false,
  extra = null,
}: PumpGridProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (pumps.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <EmptyState title={t.pumps.title} hint={t.common.emptyHint} icon={<Fuel className="h-7 w-7" />} />
        {extra ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {extra}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
      {pumps.map((pump) => (
        <PumpCard
          key={pump.id}
          pump={pump}
          live={telemetry[pump.id] ?? null}
          onSelect={onSelect}
          disabled={disabled}
        />
      ))}
      {extra}
    </div>
  );
}

export default PumpGrid;
