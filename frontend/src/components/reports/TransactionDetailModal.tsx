/**
 * Гүйлгээний дэлгэрэнгүй — тайлангийн задаргаанаас **давхар товшиход** нээгдэнэ.
 *
 * Борлуулалт дээр дарахад юу юу авсан, хэн зарсан, хэзээ, ямар төлбөрөөр,
 * нийт дүн; орлого дээр дарахад нийлүүлэгч, барааны мөрүүд, гүйлгээний утга.
 */

import { useTransactionDetail } from "../../api/queries/reportCenter";
import { t } from "../../i18n/mn";
import { formatDateTime, formatMNT, formatNumber } from "../../lib/format";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

export interface TransactionDetailModalProps {
  sourceType: string | null;
  sourceId: string | null;
  onClose: () => void;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "" || value === "—") return null;
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="text-ink-soft">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

export function TransactionDetailModal({
  sourceType,
  sourceId,
  onClose,
}: TransactionDetailModalProps) {
  const query = useTransactionDetail(sourceType, sourceId);
  const d = query.data;

  return (
    <Modal open={Boolean(sourceType && sourceId)} onClose={onClose} title={d?.title ?? t.common.loading} size="lg">
      {query.isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : d ? (
        <div className="flex flex-col gap-4">
          {/* Толгойн мэдээлэл */}
          <div className="rounded-xl bg-surface-sunken p-4">
            <Field label={t.txDetail.when} value={formatDateTime(d.when)} />
            <Field label={t.txDetail.branch} value={d.branch} />
            <Field label={d.person_label} value={d.person} />
            <Field label={t.txDetail.customer} value={d.customer} />
            <Field label={t.txDetail.supplier} value={d.supplier} />
            <Field label={t.txDetail.invoiceNo} value={d.invoice_no} />
            <Field label={t.txDetail.note} value={d.note} />
            {(d.extra ?? []).map((e) => (
              <Field
                key={e.label}
                label={e.label}
                value={typeof e.value === "number" ? formatNumber(String(e.value), 2) : e.value}
              />
            ))}
          </div>

          {/* Мөрүүд */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-line text-xs uppercase text-ink-soft">
                  <th className="py-2 text-left">{t.txDetail.item}</th>
                  <th className="py-2 text-right">{t.txDetail.qty}</th>
                  <th className="py-2 text-right">{t.txDetail.price}</th>
                  <th className="py-2 text-right">{t.txDetail.amount}</th>
                </tr>
              </thead>
              <tbody>
                {d.lines.map((line, i) => (
                  <tr key={i} className="border-b border-line">
                    <td className="py-2">{line.name}</td>
                    <td className="num py-2 text-right">
                      {line.qty ? `${formatNumber(line.qty, 2)} ${line.unit}` : "—"}
                    </td>
                    <td className="num py-2 text-right">
                      {line.unit_price ? formatMNT(line.unit_price) : "—"}
                    </td>
                    <td className="num py-2 text-right font-semibold">{formatMNT(line.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Төлбөр */}
          {d.payments.length > 0 ? (
            <div className="rounded-xl border border-line p-4">
              <div className="mb-2 text-xs font-semibold uppercase text-ink-soft">
                {t.txDetail.payments}
              </div>
              {d.payments.map((p, i) => (
                <div key={i} className="flex justify-between py-1 text-sm">
                  <span>
                    {p.method_name}
                    {p.ref_no ? <span className="ml-2 text-xs text-ink-soft">{p.ref_no}</span> : null}
                  </span>
                  <span className="num font-medium">
                    {formatMNT(p.amount)}
                    {p.received ? (
                      <span className="ml-2 text-xs text-ink-soft">
                        {t.txDetail.received} {formatMNT(p.received)} · {t.txDetail.change}{" "}
                        {formatMNT(p.change_given ?? "0")}
                      </span>
                    ) : null}
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          {/* Дүн */}
          <div className="rounded-xl bg-surface-alt p-4">
            <Field label={t.txDetail.subtotal} value={formatMNT(d.subtotal)} />
            <Field label={t.txDetail.vat} value={formatMNT(d.vat_amount)} />
            <div className="mt-2 flex justify-between border-t border-line pt-2 text-base font-bold">
              <span>{t.txDetail.total}</span>
              <span className="num">{formatMNT(d.total)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="py-8 text-center text-sm text-ink-soft">{t.txDetail.notFound}</div>
      )}
    </Modal>
  );
}

export default TransactionDetailModal;
