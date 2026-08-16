import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Activity } from "lucide-react";

import { useTank, useTankMovements } from "../../api/queries/tanks";
import type { TankMovement } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { colors, PAGE_SIZE, type Tone } from "../../lib/constants";
import { dAbs, dIsNegative, dToNumber } from "../../lib/decimal";
import { daysAgoInput, formatDate, formatDateTime, formatLiters, formatMNT, todayInput } from "../../lib/format";
import { ChipGroup, Pager } from "../catalog/_shared";

type MovementFilter = "all" | "receipt" | "sale" | "adjustment" | "variance";

const MOVEMENT_TONE: Record<string, Tone> = {
  receipt: "success",
  sale: "action",
  adjustment: "warning",
  variance: "danger",
};

const MOVEMENT_LABEL: Record<string, string> = {
  receipt: t.tanks.receipt,
  sale: t.tanks.sale,
  adjustment: t.tanks.adjustment,
  variance: t.tanks.varianceMovement,
};

const CHART_WIDTH = 720;
const CHART_HEIGHT = 200;

interface ChartPoint {
  x: number;
  y: number;
  liters: string;
  at: string;
}

/** Гараар зурсан SVG — түвшний өөрчлөлт (график сан ашиглахгүй). */
function LevelChart({ points, capacity }: { points: readonly ChartPoint[]; capacity: number }) {
  if (points.length < 2) {
    return (
      <div className="py-10">
        <EmptyState compact icon={<Activity className="h-7 w-7" />} title={t.reports.noData} hint="" />
      </div>
    );
  }

  const line = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = `${points[0].x.toFixed(1)},${CHART_HEIGHT} ${line} ${points[points.length - 1].x.toFixed(1)},${CHART_HEIGHT}`;
  const gridLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="scroll-touch overflow-x-auto">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="h-52 w-full min-w-[32rem]"
        role="img"
        aria-label={t.tanks.movements}
        preserveAspectRatio="none"
      >
        {gridLines.map((ratio) => (
          <line
            key={ratio}
            x1={0}
            x2={CHART_WIDTH}
            y1={CHART_HEIGHT * ratio}
            y2={CHART_HEIGHT * ratio}
            stroke={colors.line}
            strokeWidth={1}
          />
        ))}
        <polygon points={area} fill={colors.action} opacity={0.12} />
        <polyline
          points={line}
          fill="none"
          stroke={colors.action}
          strokeWidth={2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map((point, index) => (
          <circle
            key={`${point.at}-${index}`}
            cx={point.x}
            cy={point.y}
            r={2.5}
            fill={colors.action}
          />
        ))}
      </svg>
      <div className="flex justify-between px-1 text-xs text-ink-soft">
        <span>{formatDate(points[0].at)}</span>
        <span className="num">{formatLiters(capacity, 0)}</span>
        <span>{formatDate(points[points.length - 1].at)}</span>
      </div>
    </div>
  );
}

export function TankDetailPage() {
  const { id = "" } = useParams<{ id: string }>();

  const [range, setRange] = useState<DateRange>({ from: daysAgoInput(29), to: todayInput() });
  const [filter, setFilter] = useState<MovementFilter>("all");
  const [offset, setOffset] = useState(0);

  const tankQuery = useTank(id);
  const movementsQuery = useTankMovements(id, {
    date_from: range.from,
    date_to: range.to,
    movement_type: filter === "all" ? undefined : filter,
    limit: PAGE_SIZE,
    offset,
  });

  const tank = tankQuery.data ?? null;
  const movements = useMemo(() => movementsQuery.data?.items ?? [], [movementsQuery.data]);
  const total = movementsQuery.data?.total ?? 0;

  const chartPoints = useMemo<ChartPoint[]>(() => {
    const ordered = [...movements].reverse();
    if (ordered.length === 0) return [];

    const values = ordered.map((movement) => dToNumber(movement.balance_after_l));
    const capacity = tank ? dToNumber(tank.capacity_l) : Math.max(...values);
    const max = Math.max(capacity, ...values, 1);

    return ordered.map((movement, index) => ({
      x: ordered.length === 1 ? CHART_WIDTH / 2 : (index / (ordered.length - 1)) * CHART_WIDTH,
      y: CHART_HEIGHT - (values[index] / max) * (CHART_HEIGHT - 12) - 6,
      liters: movement.balance_after_l,
      at: movement.created_at,
    }));
  }, [movements, tank]);

  const setRangeAndReset = (next: DateRange): void => {
    setRange(next);
    setOffset(0);
  };

  const setFilterAndReset = (next: MovementFilter): void => {
    setFilter(next);
    setOffset(0);
  };

  const columns: Column<TankMovement>[] = [
    {
      key: "created_at",
      header: t.common.dateTime,
      primary: true,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "movement_type",
      header: t.tanks.movementType,
      render: (row) => (
        <StatusBadge
          size="sm"
          dot
          tone={MOVEMENT_TONE[row.movement_type] ?? "neutral"}
          label={MOVEMENT_LABEL[row.movement_type] ?? row.movement_type}
        />
      ),
    },
    {
      key: "liters",
      header: t.tanks.movements,
      align: "right",
      numeric: true,
      render: (row) => (
        <span className={dIsNegative(row.liters) ? "font-semibold text-danger-dark" : "font-semibold text-success-dark"}>
          {dIsNegative(row.liters) ? "−" : "+"}
          {formatLiters(dAbs(row.liters))}
        </span>
      ),
    },
    {
      key: "unit_cost",
      header: t.common.unitCost,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.unit_cost),
    },
    {
      key: "balance_after_l",
      header: t.tanks.balanceAfter,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatLiters(row.balance_after_l)}</span>,
    },
    {
      key: "note",
      header: t.common.note,
      hideOnMobile: true,
      render: (row) => <span className="text-ink-soft">{row.note ?? row.ref_type ?? "—"}</span>,
    },
  ];

  const pct = tank ? dToNumber(tank.fill_pct) : 0;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={tank ? tank.name : t.tanks.tank}
        subtitle={tank ? `${tank.fuel.name_mn} · ${tank.fuel.code}` : undefined}
        back="/tanks"
      />

      {tank ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatBox label={t.tanks.current} value={formatLiters(tank.current_l, 0)} tone="action" size="lg" />
            <StatBox label={t.tanks.capacity} value={formatLiters(tank.capacity_l, 0)} tone="neutral" />
            <StatBox label={t.tanks.avgCost} value={formatMNT(tank.avg_cost)} tone="neutral" />
            <StatBox label={t.tanks.stockValue} value={formatMNT(tank.stock_value)} tone="success" />
          </div>

          <Card title={t.tanks.fillPct}>
            <ProgressBar
              value={pct}
              autoTone
              size="lg"
              valueLabel={`${formatLiters(tank.current_l)} / ${formatLiters(tank.capacity_l, 0)}`}
              markerPct={
                dToNumber(tank.capacity_l) > 0
                  ? (dToNumber(tank.min_level_l) / dToNumber(tank.capacity_l)) * 100
                  : 0
              }
            />
          </Card>
        </>
      ) : null}

      <Card title={t.tanks.movements} subtitle={t.common.period}>
        <LevelChart points={chartPoints} capacity={tank ? dToNumber(tank.capacity_l) : 0} />
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <DateRangePicker value={range} onChange={setRangeAndReset} />
        <ChipGroup<MovementFilter>
          value={filter}
          onChange={setFilterAndReset}
          options={[
            { value: "all", label: t.common.all },
            { value: "receipt", label: t.tanks.receipt },
            { value: "sale", label: t.tanks.sale },
            { value: "adjustment", label: t.tanks.adjustment },
            { value: "variance", label: t.tanks.varianceMovement },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={movements}
          rowKey={(row) => row.id}
          loading={movementsQuery.isLoading}
          empty={<EmptyState title={t.reports.noData} hint={t.common.emptyHint} />}
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>
    </div>
  );
}

export default TankDetailPage;
