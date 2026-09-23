import type { ReactNode } from "react";

export interface TabItem<V> {
  value: V;
  label: string;
  icon?: ReactNode;
  badge?: number | string | null;
}

export interface TabBarProps<V> {
  value: V;
  onChange: (value: V) => void;
  items: readonly TabItem<V>[];
  /** `pill` — цайвар дэвсгэр дээр; `underline` — хуудасны толгойд. */
  variant?: "pill" | "underline";
  className?: string;
}

export function TabBar<V extends string | number>({
  value,
  onChange,
  items,
  variant = "pill",
  className = "",
}: TabBarProps<V>) {
  if (variant === "underline") {
    return (
      <div className={`scroll-touch scrollbar-none flex gap-1 overflow-x-auto border-b border-line ${className}`} role="tablist">
        {items.map((item) => {
          const active = item.value === value;
          return (
            <button
              key={String(item.value)}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(item.value)}
              className={[
                "flex h-12 shrink-0 items-center gap-2 border-b-2 px-4 text-[15px] font-semibold whitespace-nowrap transition-colors",
                active
                  ? "border-action text-action-dark"
                  : "border-transparent text-ink-soft hover:text-ink",
              ].join(" ")}
            >
              {item.icon}
              {item.label}
              {item.badge ? (
                <span className="num rounded-full bg-danger px-2 py-0.5 text-xs font-bold text-white">
                  {item.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    );
  }

  // 4 хүртэлх таб утсанд тэнцүү баганаар (дүрс дээр, бичиг доор) бүгд харагдана —
  // өмнө нь хэвтээ гүйж, сүүлийн таб тасарч, доор нь бүдүүн гүйлгэх мөр гардаг байв.
  const compact = items.length <= 4;
  return (
    <div
      className={
        compact
          ? `grid auto-cols-fr grid-flow-col gap-1 rounded-xl border border-line bg-surface-alt p-1 sm:flex sm:gap-1.5 sm:p-1.5 lg:flex-wrap ${className}`
          : `scroll-touch scrollbar-none flex gap-1.5 overflow-x-auto rounded-xl border border-line bg-surface-alt p-1.5 lg:flex-wrap lg:overflow-x-visible ${className}`
      }
      role="tablist"
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={String(item.value)}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={[
              compact
                ? "relative flex min-h-14 min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-center text-[12px] leading-tight font-semibold transition-colors sm:h-12 sm:min-h-0 sm:shrink-0 sm:flex-row sm:gap-2 sm:px-4 sm:text-[15px] sm:whitespace-nowrap"
                : "flex h-12 shrink-0 items-center gap-2 rounded-lg px-4 text-[15px] font-semibold whitespace-nowrap transition-colors",
              active ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:bg-white/60",
            ].join(" ")}
          >
            {item.icon}
            {item.label}
            {item.badge ? (
              <span className="num rounded-full bg-danger px-2 py-0.5 text-xs font-bold text-white">
                {item.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export default TabBar;
