import { useEffect, useState } from "react";
import { Delete } from "lucide-react";

import { t } from "../../i18n/mn";
import { Spinner } from "./Spinner";

export interface PinPadProps {
  onSubmit: (pin: string) => void;
  onCancel?: () => void;
  /** Автоматаар илгээх урт (анхдагч 6). Түүнээс богино ПИН-д "Нэвтрэх" товч. */
  autoSubmitLength?: number;
  minLength?: number;
  loading?: boolean;
  /** Алдааны текст — улаанаар харагдаж, шивэлт сэгсэрнэ. */
  error?: string | null;
  title?: string;
  className?: string;
}

const KEYS: readonly (string | null)[] = ["1", "2", "3", "4", "5", "6", "7", "8", "9", null, "0", "back"];

export function PinPad({
  onSubmit,
  onCancel,
  autoSubmitLength = 6,
  minLength = 4,
  loading = false,
  error = null,
  title,
  className = "",
}: PinPadProps) {
  const [pin, setPin] = useState("");
  const [shake, setShake] = useState(false);

  // Алдаа ирэхэд оруулсан ПИН-г цэвэрлэж, сэгсэрнэ.
  useEffect(() => {
    if (!error) return;
    setPin("");
    setShake(true);
    const timer = window.setTimeout(() => setShake(false), 600);
    return () => window.clearTimeout(timer);
  }, [error]);

  const submit = (candidate: string): void => {
    if (candidate.length < minLength || loading) return;
    onSubmit(candidate);
  };

  const press = (key: string): void => {
    if (loading) return;
    if (key === "back") {
      setPin((current) => current.slice(0, -1));
      return;
    }
    setPin((current) => {
      if (current.length >= autoSubmitLength) return current;
      const next = current + key;
      if (next.length === autoSubmitLength) {
        window.setTimeout(() => submit(next), 60);
      }
      return next;
    });
  };

  // Физик гар — тоо, Backspace, Enter.
  useEffect(() => {
    const handler = (event: KeyboardEvent): void => {
      if (loading) return;
      if (/^[0-9]$/.test(event.key)) {
        event.preventDefault();
        press(event.key);
        return;
      }
      if (event.key === "Backspace") {
        event.preventDefault();
        press("back");
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        submit(pin);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pin, loading]);

  const dots = Array.from({ length: autoSubmitLength }, (_, index) => index < pin.length);

  return (
    <div className={`flex w-full max-w-sm shrink-0 flex-col items-center gap-4 sm:gap-6 ${className}`}>
      {title ? <div className="text-lg font-semibold text-ink-invert">{title}</div> : null}

      <div className={`flex flex-col items-center gap-3 ${shake ? "animate-shake" : ""}`}>
        <div className="flex items-center gap-3.5">
          {dots.map((filled, index) => (
            <span
              key={index}
              className={[
                "h-4 w-4 rounded-full border-2 transition-all duration-100",
                error ? "border-danger" : "border-brand-600",
                filled ? (error ? "bg-danger" : "bg-success border-success scale-110") : "bg-transparent",
              ].join(" ")}
            />
          ))}
        </div>
        <div className="h-6 text-sm font-medium text-danger" role="alert">
          {error ?? ""}
        </div>
      </div>

      <div className="grid w-full grid-cols-3 gap-2.5 sm:gap-3">
        {KEYS.map((key, index) => {
          if (key === null) {
            return onCancel ? (
              <button
                key="cancel"
                type="button"
                onClick={onCancel}
                className="h-14 rounded-xl border border-brand-700 bg-brand-800/60 text-sm font-semibold text-ink-faint transition-colors active:bg-brand-700 sm:h-16"
              >
                {t.common.cancel}
              </button>
            ) : (
              <span key={`gap-${index}`} />
            );
          }

          if (key === "back") {
            return (
              <button
                key="back"
                type="button"
                onClick={() => press("back")}
                aria-label={t.common.delete}
                className="flex h-14 items-center justify-center rounded-xl border border-brand-700 bg-brand-800/60 text-ink-faint transition-colors active:bg-brand-700 sm:h-16"
              >
                <Delete className="h-6 w-6" />
              </button>
            );
          }

          return (
            <button
              key={key}
              type="button"
              onClick={() => press(key)}
              disabled={loading}
              className="num h-14 rounded-xl border border-brand-700 bg-brand-800 text-2xl font-bold text-ink-invert transition-colors active:bg-brand-700 disabled:opacity-50 sm:h-16"
            >
              {key}
            </button>
          );
        })}
      </div>

      {autoSubmitLength > minLength ? (
        <button
          type="button"
          onClick={() => submit(pin)}
          disabled={pin.length < minLength || loading}
          className="flex h-14 w-full items-center justify-center gap-3 rounded-xl bg-success text-lg font-bold text-white transition-colors active:bg-success-dark disabled:opacity-40 sm:h-16"
        >
          {loading ? <Spinner size="md" /> : null}
          {t.auth.enter}
        </button>
      ) : null}
    </div>
  );
}

export default PinPad;
