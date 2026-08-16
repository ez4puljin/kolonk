import { t } from "../../i18n/mn";
import { daysAgoInput, toDateInput, todayInput } from "../../lib/format";

export interface DateRange {
  from: string;
  to: string;
}

export type RangePreset = "today" | "yesterday" | "week" | "month" | "year";

export interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  /** Ямар товч харагдахыг сонгох. */
  presets?: readonly RangePreset[];
  className?: string;
}

const DEFAULT_PRESETS: readonly RangePreset[] = ["today", "yesterday", "week", "month", "year"];

const PRESET_LABEL: Record<RangePreset, string> = {
  today: t.common.today,
  yesterday: t.common.yesterday,
  week: t.common.week,
  month: t.common.month,
  year: t.common.year,
};

export function rangeFor(preset: RangePreset): DateRange {
  const now = new Date();
  switch (preset) {
    case "today":
      return { from: todayInput(), to: todayInput() };
    case "yesterday": {
      const day = daysAgoInput(1);
      return { from: day, to: day };
    }
    case "week":
      return { from: daysAgoInput(6), to: todayInput() };
    case "month":
      return { from: toDateInput(new Date(now.getFullYear(), now.getMonth(), 1)), to: todayInput() };
    case "year":
      return { from: toDateInput(new Date(now.getFullYear(), 0, 1)), to: todayInput() };
    default:
      return { from: todayInput(), to: todayInput() };
  }
}

function isSameRange(a: DateRange, b: DateRange): boolean {
  return a.from === b.from && a.to === b.to;
}

export function DateRangePicker({
  value,
  onChange,
  presets = DEFAULT_PRESETS,
  className = "",
}: DateRangePickerProps) {
  const inputClass =
    "num h-12 min-w-[9.5rem] rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink " +
    "focus:border-action focus:outline-none";

  return (
    <div className={`flex flex-wrap items-end gap-3 ${className}`}>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => {
          const range = rangeFor(preset);
          const active = isSameRange(range, value);
          return (
            <button
              key={preset}
              type="button"
              onClick={() => onChange(range)}
              className={[
                "h-12 rounded-xl border px-4 text-[15px] font-semibold transition-colors",
                active
                  ? "border-action bg-action text-white"
                  : "border-line-strong bg-white text-ink-soft hover:bg-surface-alt active:bg-surface-sunken",
              ].join(" ")}
            >
              {PRESET_LABEL[preset]}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.from}
          </span>
          <input
            type="date"
            value={value.from}
            max={value.to || undefined}
            onChange={(event) => onChange({ ...value, from: event.target.value })}
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.to}</span>
          <input
            type="date"
            value={value.to}
            min={value.from || undefined}
            onChange={(event) => onChange({ ...value, to: event.target.value })}
            className={inputClass}
          />
        </label>
      </div>
    </div>
  );
}

export default DateRangePicker;
