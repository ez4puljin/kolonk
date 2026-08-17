import type { ReactNode } from "react";
import { Pencil, Trash2 } from "lucide-react";

import type { MoneyStr, PaymentMethod, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { TENDER_BY_METHOD } from "../../lib/constants";
import { dAbs, dIsNegative, dIsZero } from "../../lib/decimal";
import { formatMNT } from "../../lib/format";
import { EmptyState } from "../ui/EmptyState";

/** Кассын дэлгэц дээрх нэг төлбөрийн мөр. */
export interface TenderLine {
  /** Дотоод түр дугаар. */
  id: string;
  method: PaymentMethod;
  amount: MoneyStr;
  /**
   * Түгээгч дүнг нь гараар тогтоосон эсэх.
   *
   * `false` үед мөр «авто» — үлдэгдэл дүнг өөртөө шингээж, нийт дүн өөрчлөгдөхөд
   * (жишээ нь гэрээний хөнгөлөлт орох) автоматаар дахин бөглөгдөнө.
   */
  manual: boolean;
  /** Бэлэн — хүлээн авсан мөнгө. */
  received: MoneyStr | null;
  contractId: UUID | null;
  contractLabel: string | null;
  /** Гэрээний литр тутмын хөнгөлөлт (түлшний дүн дахин бодоход). */
  discountPerL: MoneyStr | null;
  refNo: string | null;
}

export interface SplitTenderListProps {
  lines: readonly TenderLine[];
  remaining: MoneyStr;
  onEditAmount: (line: TenderLine) => void;
  onRemove: (id: string) => void;
  /** Мөр бүрийн нэмэлт талбарууд (гэрээ хайх, гүйлгээний дугаар, ...). */
  renderDetail?: (line: TenderLine) => ReactNode;
}

/** Хуваан төлөх мөрүүд + үлдэгдэл. */
export function SplitTenderList({
  lines,
  remaining,
  onEditAmount,
  onRemove,
  renderDetail,
}: SplitTenderListProps) {
  const settled = dIsZero(remaining);
  const overpaid = dIsNegative(remaining);

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-semibold tracking-wide text-ink-soft uppercase">{t.tender.split}</div>

      {lines.length === 0 ? (
        <EmptyState compact title={t.tender.addTender} hint={t.tender.notEnough} />
      ) : (
        <ul className="flex flex-col gap-3">
          {lines.map((line) => {
            const meta = TENDER_BY_METHOD[line.method];
            const Icon = meta.icon;
            return (
              <li
                key={line.id}
                className="overflow-hidden rounded-2xl border border-line-strong bg-white"
                style={{ borderLeftColor: meta.color, borderLeftWidth: 6 }}
              >
                <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <span
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white"
                    style={{ backgroundColor: meta.color }}
                  >
                    <Icon className="h-5 w-5" />
                  </span>

                  <span className="min-w-0 flex-1 text-base font-bold text-ink">{meta.label}</span>

                  <button
                    type="button"
                    onClick={() => onEditAmount(line)}
                    aria-label={`${meta.label} — ${t.common.amount}`}
                    className="num flex h-12 min-w-40 items-center justify-end gap-2 rounded-xl border border-line-strong bg-surface-alt px-4 text-2xl font-bold text-ink active:bg-surface-sunken"
                  >
                    {formatMNT(line.amount)}
                    <Pencil className="h-4 w-4 text-ink-faint" />
                  </button>

                  <button
                    type="button"
                    onClick={() => onRemove(line.id)}
                    aria-label={t.common.delete}
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-danger-dark active:bg-danger-soft"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>

                {renderDetail ? <div className="border-t border-line px-4 py-3">{renderDetail(line)}</div> : null}
              </li>
            );
          })}
        </ul>
      )}

      {/* Үлдэгдэл */}
      <div
        className={[
          "flex items-center justify-between gap-4 rounded-2xl border-2 px-5 py-4",
          settled
            ? "border-success bg-success-soft"
            : overpaid
              ? "border-danger bg-danger-soft"
              : "border-warning bg-warning-soft",
        ].join(" ")}
      >
        <span className="text-lg font-bold text-ink">
          {overpaid ? t.tender.overpaid : t.tender.remaining}
        </span>
        <span
          className={[
            "num text-[40px] leading-none font-black",
            settled ? "text-success-dark" : overpaid ? "text-danger-dark" : "text-warning-dark",
          ].join(" ")}
        >
          {formatMNT(dAbs(remaining))}
        </span>
      </div>
    </div>
  );
}

export default SplitTenderList;
