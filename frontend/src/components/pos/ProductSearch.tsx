import { useRef, type ChangeEvent, type KeyboardEvent } from "react";
import { ScanLine, Search, X } from "lucide-react";

import { t } from "../../i18n/mn";

export interface ProductSearchProps {
  value: string;
  onChange: (value: string) => void;
  /** Enter эсвэл штрих код уншигчийн бүрэн мөр ирэхэд. */
  onSubmit: (value: string) => void;
  autoFocus?: boolean;
  className?: string;
}

/**
 * Кассын цорын ганц бичих талбар — нэр/SKU хайлт ба штрих код.
 *
 * Уншигч ихэвчлэн бүтэн мөрөө хурдан "бичээд" Enter дардаг тул Enter дээр
 * `onSubmit` дуудна. Мөн зөвхөн цифрээс бүрдсэн 8-14 оронтой утга бичигдмэгц
 * шууд `onSubmit` дуудаж, гар оролт хүлээхгүй.
 */
export function ProductSearch({
  value,
  onChange,
  onSubmit,
  autoFocus = false,
  className = "",
}: ProductSearchProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const lastAutoRef = useRef<string>("");

  const handleChange = (event: ChangeEvent<HTMLInputElement>): void => {
    const next = event.target.value;
    onChange(next);

    const trimmed = next.trim();
    if (/^\d{8,14}$/.test(trimmed) && trimmed !== lastAutoRef.current) {
      lastAutoRef.current = trimmed;
      onSubmit(trimmed);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed !== "") onSubmit(trimmed);
  };

  return (
    <div className={`relative flex items-center ${className}`}>
      <Search className="pointer-events-none absolute left-4 h-5 w-5 text-ink-faint" aria-hidden="true" />

      <input
        ref={inputRef}
        type="search"
        inputMode="search"
        autoComplete="off"
        autoFocus={autoFocus}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        aria-label={t.pos.barcodePrompt}
        placeholder={t.pos.barcodePrompt}
        className="h-14 w-full rounded-xl border border-line-strong bg-white pr-24 pl-12 text-base text-ink outline-none placeholder:text-ink-faint focus:border-action"
      />

      {value !== "" ? (
        <button
          type="button"
          onClick={() => {
            lastAutoRef.current = "";
            onChange("");
            inputRef.current?.focus();
          }}
          aria-label={t.common.clear}
          className="absolute right-14 flex h-12 w-12 items-center justify-center rounded-xl text-ink-soft active:bg-surface-sunken"
        >
          <X className="h-5 w-5" />
        </button>
      ) : null}

      <span
        className="pointer-events-none absolute right-4 flex h-9 w-9 items-center justify-center rounded-lg bg-surface-alt text-ink-faint"
        aria-hidden="true"
      >
        <ScanLine className="h-5 w-5" />
      </span>
    </div>
  );
}

export default ProductSearch;
