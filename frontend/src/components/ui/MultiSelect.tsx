/**
 * Олон утга сонгох талбар — тайлангийн шүүлтэд зориулсан.
 *
 * Зан төлөв: юу ч сонгоогүй бол **"Бүгд"** гэсэн утгатай (шүүлт хийхгүй).
 * Хуруугаар ажиллахад тохирсон том мөрүүд, сонгосон утгуудыг чип болгон
 * дээр нь харуулна.
 */

import { useMemo, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

import { t } from "../../i18n/mn";

export interface MultiSelectOption<V extends string> {
  value: V;
  label: string;
  hint?: string;
}

export interface MultiSelectProps<V extends string> {
  label: string;
  values: V[];
  onChange: (values: V[]) => void;
  options: readonly MultiSelectOption<V>[];
  /** Жагсаалт урт үед хайх талбар гаргана. */
  searchable?: boolean;
  placeholder?: string;
  className?: string;
}

export function MultiSelect<V extends string>({
  label,
  values,
  onChange,
  options,
  searchable,
  placeholder,
  className = "",
}: MultiSelectProps<V>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const showSearch = searchable ?? options.length > 10;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(needle) ||
        (o.hint ?? "").toLowerCase().includes(needle),
    );
  }, [options, query]);

  const selectedLabels = useMemo(
    () => options.filter((o) => values.includes(o.value)),
    [options, values],
  );

  const toggle = (value: V): void => {
    onChange(values.includes(value) ? values.filter((v) => v !== value) : [...values, value]);
  };

  return (
    <div className={className}>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-soft">
        {label}
      </div>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-14 w-full items-center justify-between gap-3 rounded-xl border-2 border-line bg-surface px-4 text-left"
      >
        <span className="flex-1 truncate text-sm">
          {values.length === 0 ? (
            <span className="text-ink-soft">{placeholder ?? t.common.all}</span>
          ) : (
            <span className="font-medium text-ink">
              {values.length === 1
                ? selectedLabels[0]?.label
                : `${values.length} ${t.multiSelect.selectedSuffix}`}
            </span>
          )}
        </span>
        {values.length > 0 ? (
          <span
            role="button"
            tabIndex={0}
            aria-label={t.multiSelect.clear}
            onClick={(e) => {
              e.stopPropagation();
              onChange([]);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.stopPropagation();
                onChange([]);
              }
            }}
            className="rounded-lg p-1 text-ink-soft hover:bg-surface-sunken"
          >
            <X className="h-4 w-4" />
          </span>
        ) : null}
        <ChevronDown className={`h-5 w-5 text-ink-soft transition ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Сонгосон утгууд — чип */}
      {values.length > 1 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selectedLabels.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => toggle(o.value)}
              className="flex items-center gap-1 rounded-lg bg-action-soft px-2 py-1 text-xs font-medium text-action-dark"
            >
              {o.label}
              <X className="h-3 w-3" />
            </button>
          ))}
        </div>
      ) : null}

      {open ? (
        <div className="mt-2 rounded-xl border-2 border-line bg-surface">
          {showSearch ? (
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.common.search}
              className="w-full border-b border-line bg-transparent px-4 py-3 text-sm outline-none"
            />
          ) : null}

          <div className="flex items-center justify-between border-b border-line px-4 py-2 text-xs">
            <button
              type="button"
              onClick={() => onChange(visible.map((o) => o.value))}
              className="font-semibold text-action"
            >
              {t.multiSelect.selectAll}
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              className="font-semibold text-ink-soft"
            >
              {t.multiSelect.clear}
            </button>
          </div>

          <div className="max-h-64 overflow-y-auto">
            {visible.map((o) => {
              const checked = values.includes(o.value);
              return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => toggle(o.value)}
                  className={`flex min-h-12 w-full items-center gap-3 px-4 text-left text-sm transition ${
                    checked ? "bg-action-soft" : "hover:bg-surface-sunken"
                  }`}
                >
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 ${
                      checked ? "border-action bg-action text-white" : "border-line-strong"
                    }`}
                  >
                    {checked ? <Check className="h-3.5 w-3.5" /> : null}
                  </span>
                  <span className="flex-1 truncate">
                    {o.label}
                    {o.hint ? <span className="ml-2 text-xs text-ink-soft">{o.hint}</span> : null}
                  </span>
                </button>
              );
            })}
            {visible.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-ink-soft">{t.common.none}</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default MultiSelect;
