import { useState } from "react";
import { Delete, X } from "lucide-react";

import { t } from "../../i18n/mn";
import { formatNumber } from "../../lib/format";

export interface NumPadProps {
  /** Хяналттай утга — string decimal ("1250.50"). */
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  onCancel?: () => void;
  /** Аравтын цэг зөвшөөрөх эсэх. */
  allowDecimal?: boolean;
  maxDecimals?: number;
  /** Дүнгийн ард харагдах нэгж ("₮", "л", "ш"). */
  suffix?: string;
  label?: string;
  submitLabel?: string;
  submitDisabled?: boolean;
  /** Түргэн товчнууд (жишээ: 5000 / 10000 / 20000). */
  quick?: readonly number[];
  className?: string;
}

const KEYS: readonly string[] = ["7", "8", "9", "4", "5", "6", "1", "2", "3"];

export function NumPad({
  value,
  onChange,
  onSubmit,
  onCancel,
  allowDecimal = true,
  maxDecimals = 2,
  suffix = "",
  label,
  submitLabel,
  submitDisabled = false,
  quick,
  className = "",
}: NumPadProps) {
  /**
   * Кассын гарын стандарт зан төлөв: цонх нээгдэхэд байсан утга (жишээ нь
   * талбарын одоогийн "0.00") эхний товшилтоор БҮТНЭЭРЭЭ солигдоно.
   *
   * Үүнгүйгээр "0.00" гэх мэт аль хэдийн 2 аравтын оронтой утга дээр
   * аравтын оронгийн хязгаар цифр оруулахыг бүрмөсөн блоклодог.
   */
  const [touched, setTouched] = useState(false);

  const appendDigit = (digit: string): void => {
    if (!touched) {
      setTouched(true);
      onChange(digit === "00" ? "0" : digit);
      return;
    }
    const dot = value.indexOf(".");
    if (dot >= 0 && value.length - dot - 1 >= maxDecimals) return;
    if (value === "0" && digit !== "00") {
      onChange(digit);
      return;
    }
    if (value === "0" && digit === "00") return;
    if (value.replace(/[^\d]/g, "").length >= 12) return;
    onChange(value + digit);
  };

  const appendDot = (): void => {
    if (!allowDecimal) return;
    if (!touched) {
      setTouched(true);
      onChange("0.");
      return;
    }
    if (value.includes(".")) return;
    onChange(value === "" ? "0." : `${value}.`);
  };

  const backspace = (): void => {
    setTouched(true);
    onChange(value.slice(0, -1));
  };

  const clear = (): void => {
    setTouched(true);
    onChange("");
  };

  const setQuick = (amount: number): void => {
    setTouched(true);
    onChange(String(amount));
  };

  const display = value === "" ? "0" : value;
  const [intPart, fracPart] = display.split(".");
  const pretty = fracPart === undefined ? formatNumber(intPart, 0) : `${formatNumber(intPart, 0)}.${fracPart}`;

  // Өндөр нь дэлгэцээс хамаарч агшина — намхан утсанд NumPad бүтэн багтана.
  const keyClass =
    "h-[clamp(3rem,6.5svh,4rem)] rounded-xl border border-line-strong bg-white text-2xl font-semibold text-ink " +
    "transition-colors active:bg-surface-sunken hover:bg-surface-alt select-none";

  return (
    <div className={`flex w-full flex-col gap-3 ${className}`}>
      {label ? <div className="text-sm font-medium text-ink-soft">{label}</div> : null}

      <div className="flex min-h-16 items-center justify-end rounded-xl border border-line-strong bg-surface-alt px-4 py-2.5 sm:min-h-[72px] sm:px-5 sm:py-3">
        {/* Урт миль (12 орон + бутархай) утсанд ч бүтэн харагдана */}
        <span className="num truncate text-[clamp(1.625rem,8.5vw,2.5rem)] leading-none font-bold text-ink">
          {pretty}
        </span>
        {suffix ? <span className="ml-2 text-xl font-semibold text-ink-soft sm:text-2xl">{suffix}</span> : null}
      </div>

      {quick && quick.length > 0 ? (
        <div className="grid grid-cols-3 gap-2">
          {quick.map((amount) => (
            <button
              key={amount}
              type="button"
              onClick={() => setQuick(amount)}
              className="num h-12 rounded-xl border border-action/25 bg-action-soft text-base font-semibold text-action-dark active:bg-action/20"
            >
              {formatNumber(amount, 0)}
            </button>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-2.5">
        {KEYS.map((key) => (
          <button key={key} type="button" className={keyClass} onClick={() => appendDigit(key)}>
            {key}
          </button>
        ))}

        <button
          type="button"
          className={keyClass}
          onClick={allowDecimal ? appendDot : () => appendDigit("00")}
        >
          {allowDecimal ? "." : "00"}
        </button>
        <button type="button" className={keyClass} onClick={() => appendDigit("0")}>
          0
        </button>
        <button
          type="button"
          className={keyClass}
          onClick={allowDecimal ? () => appendDigit("00") : backspace}
          aria-label={allowDecimal ? "00" : t.common.delete}
        >
          {allowDecimal ? "00" : <Delete className="mx-auto h-6 w-6" />}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <button
          type="button"
          onClick={clear}
          className="h-[clamp(2.75rem,5.5svh,3.5rem)] rounded-xl border border-line-strong bg-white text-base font-semibold text-ink-soft active:bg-surface-sunken"
        >
          <span className="inline-flex items-center justify-center gap-2">
            <X className="h-5 w-5" />
            {t.common.clear}
          </span>
        </button>
        <button
          type="button"
          onClick={backspace}
          className="h-[clamp(2.75rem,5.5svh,3.5rem)] rounded-xl border border-line-strong bg-white text-base font-semibold text-ink-soft active:bg-surface-sunken"
        >
          <span className="inline-flex items-center justify-center gap-2">
            <Delete className="h-5 w-5" />
            {t.common.delete}
          </span>
        </button>
      </div>

      {(onSubmit || onCancel) && (
        <div className={`grid gap-2.5 ${onCancel && onSubmit ? "grid-cols-2" : "grid-cols-1"}`}>
          {onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="h-[clamp(3rem,6.5svh,4rem)] rounded-xl border border-line-strong bg-white text-lg font-semibold text-ink active:bg-surface-sunken"
            >
              {t.common.cancel}
            </button>
          ) : null}
          {onSubmit ? (
            <button
              type="button"
              onClick={onSubmit}
              disabled={submitDisabled}
              className="h-[clamp(3rem,6.5svh,4rem)] rounded-xl bg-success text-lg font-bold text-white transition-colors active:bg-success-dark disabled:pointer-events-none disabled:opacity-45"
            >
              {submitLabel ?? t.common.confirm}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default NumPad;
