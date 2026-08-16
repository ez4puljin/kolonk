import { Layers } from "lucide-react";

import type { PaymentMethod } from "../../api/types";
import { t } from "../../i18n/mn";
import { TENDER_METHODS } from "../../lib/constants";

export interface TenderPadProps {
  onPick: (method: PaymentMethod) => void;
  /** «Хосолсон» — хоёр хэрэгслээр хуваан төлөх горимыг шууд эхлүүлнэ. */
  onSplit?: () => void;
  /** Үлдэгдэл 0 болсон үед бүх плитка идэвхгүй. */
  disabled?: boolean;
  /** Аль хэдийн ашигласан хэрэгслүүд — тэмдэглэгээ. */
  used?: readonly PaymentMethod[];
  /**
   * Салбарт зөвшөөрөгдсөн хэрэгслүүд. Өгөөгүй бол бүгд харагдана —
   * тохиргоо ачаалагдаагүй байхад товч алга болохоос сэргийлнэ.
   */
  allowed?: readonly PaymentMethod[] | null;
}

/** Төлбөрийн хэрэгслийн том плиткууд + хосолсон төлбөрийн товч. */
export function TenderPad({
  onPick,
  onSplit,
  disabled = false,
  used = [],
  allowed = null,
}: TenderPadProps) {
  const methods =
    allowed === null ? TENDER_METHODS : TENDER_METHODS.filter((meta) => allowed.includes(meta.value));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
          {t.tender.title}
        </span>
        {onSplit ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onSplit}
            className="flex h-11 items-center gap-2 rounded-xl border-2 border-action px-4 text-[15px] font-bold text-action-dark transition-colors hover:bg-action-soft disabled:pointer-events-none disabled:opacity-40"
          >
            <Layers className="h-5 w-5" />
            {t.tender.combined}
          </button>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {methods.map((meta) => {
          const Icon = meta.icon;
          const active = used.includes(meta.value);
          return (
            <button
              key={meta.value}
              type="button"
              disabled={disabled}
              onClick={() => onPick(meta.value)}
              className={[
                "relative flex min-h-24 flex-col items-center justify-center gap-2 overflow-hidden rounded-2xl border-2 bg-white px-3 py-4 transition-colors",
                "disabled:pointer-events-none disabled:opacity-40",
                active ? "ring-2" : "",
                "hover:bg-surface-alt active:bg-surface-sunken",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{ borderColor: meta.color, ...(active ? { boxShadow: `0 0 0 3px ${meta.color}55` } : {}) }}
            >
              <span
                className="flex h-11 w-11 items-center justify-center rounded-xl text-white"
                style={{ backgroundColor: meta.color }}
              >
                <Icon className="h-6 w-6" />
              </span>
              <span className="text-base font-bold text-ink">{meta.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default TenderPad;
