/**
 * WP11 — ар талын дэлгэцүүдийн хуваалцсан жижиг элементүүд.
 *
 * Энд зөвхөн хуудсуудын давхардлыг арилгах туслах компонентууд байна.
 * Бүх тоон оролт `stores/ui.ts`-ийн NumPad хүсэлтээр дамжина — гараас
 * шивэхийг зөвшөөрөхгүй (CONTRACTS.md §9).
 */

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Calculator, Check, ChevronLeft, ChevronRight, Search } from "lucide-react";

import { Modal } from "../../components/ui/Modal";
import { NumPad } from "../../components/ui/NumPad";
import { t } from "../../i18n/mn";
import { formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";

// --------------------------------------------------------------------------
// Туслах функцууд
// --------------------------------------------------------------------------

/** "12345.67" → "12 345.67" (хэрэглэгчийн шивсэн бутархайг хэвээр үлдээнэ). */
export function prettyDecimal(raw: string): string {
  if (raw === "") return "0";
  const [intPart, fracPart] = raw.split(".");
  const head = formatNumber(intPart === "" ? "0" : intPart, 0);
  return fracPart === undefined ? head : `${head}.${fracPart}`;
}

/** Хайлтын мөрийг олон талбартай тулгана (сервер талд хайлт байхгүй үед). */
export function matchesQuery(fields: readonly (string | null | undefined)[], query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (needle === "") return true;
  return fields.some((field) => (field ?? "").toLowerCase().includes(needle));
}

/** Оролтыг хойшлуулж, шивэх бүрд сервер рүү дуудахаас сэргийлнэ. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// --------------------------------------------------------------------------
// Талбарууд
// --------------------------------------------------------------------------

const INPUT_CLASS =
  "h-12 w-full rounded-xl border border-line-strong bg-white px-3.5 text-[15px] text-ink " +
  "focus:border-action focus:outline-none disabled:bg-surface-alt disabled:text-ink-faint";

export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{children}</span>;
}

export interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: ReactNode;
  disabled?: boolean;
  maxLength?: number;
  className?: string;
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  hint,
  disabled = false,
  maxLength,
  className = "",
}: TextFieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <FieldLabel>{label}</FieldLabel>
      <input
        type="text"
        value={value}
        disabled={disabled}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={INPUT_CLASS}
      />
      {hint ? <span className="text-xs text-ink-soft">{hint}</span> : null}
    </div>
  );
}

export interface TextAreaFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  className?: string;
}

export function TextAreaField({
  label,
  value,
  onChange,
  rows = 3,
  placeholder,
  className = "",
}: TextAreaFieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <FieldLabel>{label}</FieldLabel>
      <textarea
        value={value}
        rows={rows}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-line-strong bg-white px-3.5 py-2.5 text-[15px] text-ink focus:border-action focus:outline-none"
      />
    </div>
  );
}

export interface DateFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  className?: string;
}

export function DateField({ label, value, onChange, min, max, className = "" }: DateFieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <FieldLabel>{label}</FieldLabel>
      <input
        type="date"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        className={`num ${INPUT_CLASS}`}
      />
    </div>
  );
}

export interface NumberFieldProps {
  /** NumPad хүсэлтийн давтагдашгүй түлхүүр. */
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  allowDecimal?: boolean;
  maxDecimals?: number;
  quick?: readonly number[];
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}

/** Тоон талбар — дарахад дэлгэцийн NumPad нээгдэнэ (гараас шивэхгүй). */
export function NumberField({
  name,
  label,
  value,
  onChange,
  suffix = "",
  allowDecimal = true,
  maxDecimals = 2,
  quick,
  hint,
  disabled = false,
  className = "",
}: NumberFieldProps) {
  const numpad = useUiStore((state) => state.numpad);
  const openNumPad = useUiStore((state) => state.openNumPad);
  const setNumPadValue = useUiStore((state) => state.setNumPadValue);
  const closeNumPad = useUiStore((state) => state.closeNumPad);

  const open = numpad !== null && numpad.target === name;

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <FieldLabel>{label}</FieldLabel>
      <button
        type="button"
        disabled={disabled}
        onClick={() => openNumPad({ target: name, title: label, value, allowDecimal, suffix })}
        className="flex h-12 w-full items-center justify-between gap-3 rounded-xl border border-line-strong bg-white px-3.5 text-left transition-colors hover:bg-surface-alt active:bg-surface-sunken disabled:pointer-events-none disabled:bg-surface-alt sm:h-14 sm:px-4"
      >
        <Calculator className="h-5 w-5 shrink-0 text-ink-faint" />
        <span className="num flex min-w-0 items-baseline gap-1.5 truncate text-lg font-bold text-ink sm:text-xl">
          {prettyDecimal(value)}
          {suffix ? <span className="text-sm font-semibold text-ink-soft sm:text-base">{suffix}</span> : null}
        </span>
      </button>
      {hint ? <span className="text-xs text-ink-soft">{hint}</span> : null}

      <Modal open={open} onClose={closeNumPad} size="sm" title={label}>
        <NumPad
          value={numpad?.value ?? ""}
          onChange={setNumPadValue}
          allowDecimal={allowDecimal}
          maxDecimals={maxDecimals}
          suffix={suffix}
          quick={quick}
          onCancel={closeNumPad}
          onSubmit={() => {
            onChange(numpad?.value ?? "");
            closeNumPad();
          }}
        />
      </Modal>
    </div>
  );
}

export interface PickerOption {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

export interface PickerFieldProps {
  label: string;
  value: string | null;
  options: readonly PickerOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  searchable?: boolean;
  disabled?: boolean;
  className?: string;
}

/** Урт жагсаалтаас сонгох — хүрэлтэнд ээлтэй бүтэн дэлгэцийн сонголт. */
export function PickerField({
  label,
  value,
  options,
  onChange,
  placeholder,
  searchable = true,
  disabled = false,
  className = "",
}: PickerFieldProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = options.find((option) => option.value === value) ?? null;
  const filtered = useMemo(
    () => options.filter((option) => matchesQuery([option.label, option.hint], query)),
    [options, query],
  );

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <FieldLabel>{label}</FieldLabel>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          setQuery("");
          setOpen(true);
        }}
        className="flex h-12 w-full items-center justify-between gap-3 rounded-xl border border-line-strong bg-white px-3.5 text-left transition-colors hover:bg-surface-alt active:bg-surface-sunken disabled:pointer-events-none disabled:bg-surface-alt"
      >
        <span className={`min-w-0 flex-1 truncate text-[15px] ${selected ? "text-ink" : "text-ink-faint"}`}>
          {selected?.label ?? placeholder ?? t.common.select}
        </span>
        <ChevronRight className="h-5 w-5 shrink-0 text-ink-faint" />
      </button>

      <Modal open={open} onClose={() => setOpen(false)} size="md" title={label}>
        <div className="flex flex-col gap-3">
          {searchable ? (
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3.5 h-5 w-5 -translate-y-1/2 text-ink-faint" />
              <input
                type="text"
                value={query}
                placeholder={t.common.searchPlaceholder}
                onChange={(event) => setQuery(event.target.value)}
                className={`${INPUT_CLASS} pl-11`}
              />
            </div>
          ) : null}

          {filtered.length === 0 ? (
            <div className="py-10 text-center text-sm text-ink-soft">{t.common.empty}</div>
          ) : (
            <div className="flex flex-col gap-2">
              {filtered.map((option) => {
                const active = option.value === value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    disabled={option.disabled}
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                    className={[
                      "flex min-h-14 items-center gap-3 rounded-xl border px-4 py-2.5 text-left transition-colors",
                      active
                        ? "border-action bg-action-soft"
                        : "border-line-strong bg-white hover:bg-surface-alt active:bg-surface-sunken",
                      option.disabled ? "pointer-events-none opacity-40" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px] font-semibold text-ink">{option.label}</span>
                      {option.hint ? (
                        <span className="num block truncate text-sm text-ink-soft">{option.hint}</span>
                      ) : null}
                    </span>
                    {active ? <Check className="h-5 w-5 shrink-0 text-action" /> : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}

export interface ToggleFieldProps {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  hint?: string;
  className?: string;
}

export function ToggleField({ label, value, onChange, hint, className = "" }: ToggleFieldProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      onClick={() => onChange(!value)}
      className={`flex min-h-14 w-full items-center gap-4 rounded-xl border border-line-strong bg-white px-4 py-2.5 text-left transition-colors hover:bg-surface-alt ${className}`}
    >
      <span className="min-w-0 flex-1">
        {/* `truncate` ЗОРИУД алга: утсанд тохиргооны нэр, тайлбар нь
            179px-д шахагдаж 30% нь л харагддаг байв — хэрэглэгч уг
            унтраалга юу хийхийг мэдэх аргагүй болно. */}
        <span className="block text-[15px] font-semibold text-ink">{label}</span>
        {hint ? <span className="block text-xs text-ink-soft">{hint}</span> : null}
      </span>
      <span
        className={`flex h-8 w-14 shrink-0 items-center rounded-full p-1 transition-colors ${value ? "bg-success" : "bg-surface-sunken"}`}
      >
        <span
          className={`h-6 w-6 rounded-full bg-white shadow transition-transform ${value ? "translate-x-6" : "translate-x-0"}`}
        />
      </span>
    </button>
  );
}

// --------------------------------------------------------------------------
// Шүүлтүүр, хуудаслалт
// --------------------------------------------------------------------------

export interface ChipOption<V extends string> {
  value: V;
  label: string;
  badge?: number | null;
}

export interface ChipGroupProps<V extends string> {
  value: V;
  onChange: (value: V) => void;
  options: readonly ChipOption<V>[];
  label?: string;
  className?: string;
}

export function ChipGroup<V extends string>({
  value,
  onChange,
  options,
  label,
  className = "",
}: ChipGroupProps<V>) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              className={[
                "flex h-12 items-center gap-2 rounded-xl border px-4 text-[15px] font-semibold transition-colors",
                active
                  ? "border-action bg-action text-white"
                  : "border-line-strong bg-white text-ink-soft hover:bg-surface-alt active:bg-surface-sunken",
              ].join(" ")}
            >
              {option.label}
              {option.badge ? (
                <span
                  className={`num rounded-full px-2 py-0.5 text-xs font-bold ${active ? "bg-white/25 text-white" : "bg-danger text-white"}`}
                >
                  {option.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchInput({ value, onChange, placeholder, className = "" }: SearchInputProps) {
  return (
    <div className={`relative min-w-[14rem] ${className}`}>
      <Search className="pointer-events-none absolute top-1/2 left-3.5 h-5 w-5 -translate-y-1/2 text-ink-faint" />
      <input
        type="text"
        value={value}
        placeholder={placeholder ?? t.common.searchPlaceholder}
        onChange={(event) => onChange(event.target.value)}
        className={`${INPUT_CLASS} pl-11`}
      />
    </div>
  );
}

export interface PagerProps {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
  className?: string;
}

/** Серверийн хуудаслалт — `?limit=&offset=`. */
export function Pager({ offset, limit, total, onChange, className = "" }: PagerProps) {
  if (total <= limit) return null;

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 ${className}`}>
      <span className="num text-sm text-ink-soft">
        {from}–{to} {t.common.of} {formatNumber(total, 0)} {t.common.rows}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={offset <= 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          aria-label={t.common.prev}
          className="flex h-12 w-12 items-center justify-center rounded-xl border border-line-strong bg-white text-ink transition-colors hover:bg-surface-alt disabled:pointer-events-none disabled:opacity-40"
        >
          <ChevronLeft className="h-6 w-6" />
        </button>
        <button
          type="button"
          disabled={to >= total}
          onClick={() => onChange(offset + limit)}
          aria-label={t.common.next}
          className="flex h-12 w-12 items-center justify-center rounded-xl border border-line-strong bg-white text-ink transition-colors hover:bg-surface-alt disabled:pointer-events-none disabled:opacity-40"
        >
          <ChevronRight className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// Дэлгэрэнгүй харуулах
// --------------------------------------------------------------------------

export function KeyValue({
  label,
  value,
  numeric = false,
  className = "",
}: {
  label: string;
  value: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      <span className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">{label}</span>
      <span className={`text-[15px] font-semibold text-ink ${numeric ? "num" : ""}`}>{value}</span>
    </div>
  );
}

/** Хуудасны толгойн доорх шүүлтүүрийн эгнээ. */
export function FilterBar({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5 ${className}`}
    >
      {children}
    </div>
  );
}
