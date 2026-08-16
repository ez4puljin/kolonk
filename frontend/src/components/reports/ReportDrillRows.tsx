/**
 * Тайлангийн мөрийн задаргаа — уг мөрийн доор шууд дэлгэгдэнэ.
 *
 * Мөр дээр **давхар товшиход** энэ хэсэг гарч ирнэ. Задаргааны мөр дээр дахин
 * давхар товшвол тухайн гүйлгээний дэлгэрэнгүй цонх нээгдэнэ.
 */

import { useReportDrill } from "../../api/queries/reportCenter";
import type { ReportCenterParams } from "../../api/types";
import { t } from "../../i18n/mn";
import { formatDate, formatMNT, formatNumber } from "../../lib/format";

export interface ReportDrillRowsProps {
  params: ReportCenterParams;
  path: string[];
  /** Эх мөрийн түвшин — догол мөрийг тааруулна. */
  level: number;
  onOpenTransaction: (sourceType: string, sourceId: string) => void;
}

export function ReportDrillRows({
  params,
  path,
  level,
  onOpenTransaction,
}: ReportDrillRowsProps) {
  const query = useReportDrill(params, path);
  const indent = `${(level + 1) * 1.25}rem`;

  if (query.isLoading) {
    return (
      <tr>
        <td colSpan={4} className="border border-line px-3 py-2 text-xs text-ink-soft">
          <span style={{ paddingLeft: indent }}>{t.common.loading}</span>
        </td>
      </tr>
    );
  }

  const data = query.data;
  if (!data || data.items.length === 0) {
    return (
      <tr>
        <td colSpan={4} className="border border-line px-3 py-2 text-xs text-ink-soft">
          <span style={{ paddingLeft: indent }}>{t.reportCenter.noDetails}</span>
        </td>
      </tr>
    );
  }

  return (
    <>
      {data.items.map((det, i) => (
        <tr
          key={`${path.join("/")}-${i}`}
          onDoubleClick={() =>
            det.source_id && onOpenTransaction(det.source_type, det.source_id)
          }
          title={t.reportCenter.doubleClickTransaction}
          className="cursor-pointer bg-surface-alt/40 text-xs text-ink-soft hover:bg-action-soft"
        >
          <td className="border border-line px-3 py-1">
            <span style={{ paddingLeft: indent }}>
              {formatDate(det.date)} · {det.tx_type_name} {det.doc_no} — {det.item_name}
              {det.employee_name && det.employee_name !== "—" ? ` (${det.employee_name})` : ""}
            </span>
          </td>
          <td className="num border border-line px-3 py-1 text-right">
            {Number(det.qty) === 0 ? "" : `${formatNumber(det.qty, 2)} ${det.unit}`}
          </td>
          <td className="num border border-line px-3 py-1 text-right">{formatMNT(det.amount)}</td>
          <td className="border border-line px-3 py-1" />
        </tr>
      ))}
      {data.truncated ? (
        <tr>
          <td colSpan={4} className="border border-line px-3 py-1 text-xs italic text-warning-dark">
            <span style={{ paddingLeft: indent }}>
              {t.reportCenter.truncated.replace("{shown}", String(data.items.length)).replace(
                "{total}",
                String(data.total),
              )}
            </span>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export default ReportDrillRows;
