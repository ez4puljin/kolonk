import type { ReceiptPayload } from "../../api/types";
import { t } from "../../i18n/mn";
import { formatDateTime, formatMoneyExact, formatQty } from "../../lib/format";

import "./print.css";

export interface ReceiptTemplateProps {
  receipt: ReceiptPayload;
  /** Дахин хэвлэлт эсэх — толгойд тэмдэглэгээ нэмнэ. */
  reprint?: boolean;
}

/** `qr_data` нь зураг мөн эсэх (data:image/... эсвэл .png/.svg төгсгөлтэй URL). */
function isImageSource(value: string): boolean {
  const raw = value.trim();
  if (raw.startsWith("data:image/")) return true;
  return /^https?:\/\/\S+\.(png|jpe?g|gif|svg|webp)(\?\S*)?$/i.test(raw);
}

function Line({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`rc-row${strong ? " rc-strong" : ""}`}>
      <span>{label}</span>
      <span className="rc-num">{value}</span>
    </div>
  );
}

/**
 * 80мм дулааны принтерийн баримт (агуулга 72мм).
 *
 * `usePrint().print(<ReceiptTemplate receipt={...} />)` хэлбэрээр дуудна.
 */
export function ReceiptTemplate({ receipt, reprint = false }: ReceiptTemplateProps) {
  const station = receipt.station;
  const ebarimt = receipt.ebarimt;
  const qr = ebarimt?.qr_data ?? null;
  const showQrImage = qr !== null && qr.trim() !== "" && isImageSource(qr);

  return (
    <div className="rc-sheet print-sheet">
      {/* --- Толгой --- */}
      <div className="rc-center">
        <div className="rc-station">{station.name}</div>
        {station.address ? <div className="rc-muted">{station.address}</div> : null}
        {station.phone ? (
          <div className="rc-muted">
            {t.common.phone}: {station.phone}
          </div>
        ) : null}
        {station.vat_payer_no ? (
          <div className="rc-muted">
            {t.admin.vatPayerNo}: {station.vat_payer_no}
          </div>
        ) : null}
      </div>

      <hr className="rc-rule" />

      <Line label={t.sales.saleNo} value={String(receipt.number)} strong />
      <Line label={t.common.dateTime} value={formatDateTime(receipt.sold_at)} />
      {receipt.cashier_name ? <Line label={t.sales.cashier} value={receipt.cashier_name} /> : null}
      {receipt.shift_number !== null ? (
        <Line label={t.shift.number} value={String(receipt.shift_number)} />
      ) : null}
      {receipt.customer_name ? <Line label={t.partners.customer} value={receipt.customer_name} /> : null}
      {receipt.contract_no ? <Line label={t.partners.contractNo} value={receipt.contract_no} /> : null}
      {reprint ? <div className="rc-center rc-strong rc-muted">{t.sales.reprint}</div> : null}

      <hr className="rc-rule" />

      {/* --- Мөрүүд --- */}
      {receipt.items.map((item) => (
        <div className="rc-item" key={item.line_no}>
          <div className="rc-item-name">
            {item.line_no}. {item.name}
          </div>
          <div className="rc-row rc-item-calc">
            <span className="rc-num">
              {formatQty(item.qty, item.unit)} × {formatMoneyExact(item.unit_price, false)}
            </span>
            <span className="rc-num rc-strong">{formatMoneyExact(item.amount, false)}</span>
          </div>
        </div>
      ))}

      <hr className="rc-rule" />

      <Line label={t.common.net} value={formatMoneyExact(receipt.subtotal, false)} />
      <Line label={t.common.vat} value={formatMoneyExact(receipt.vat_amount, false)} />

      <hr className="rc-rule-solid" />

      <div className="rc-row rc-total">
        <span>{t.common.total}</span>
        <span className="rc-num">{formatMoneyExact(receipt.total, false)}</span>
      </div>

      <hr className="rc-rule" />

      {/* --- Төлбөр --- */}
      {receipt.payments.map((payment, index) => (
        <div key={`${payment.method}-${index}`}>
          <Line label={payment.method_name} value={formatMoneyExact(payment.amount, false)} />
          {payment.received !== null && payment.received !== undefined ? (
            <Line label={t.tender.received} value={formatMoneyExact(payment.received, false)} />
          ) : null}
        </div>
      ))}

      <Line label={t.tender.change} value={formatMoneyExact(receipt.change_total, false)} strong />

      {/* --- И-баримт --- */}
      {ebarimt ? (
        <>
          <hr className="rc-rule" />
          <div className="rc-center">
            <div className="rc-strong">{t.sales.ebarimt}</div>
            {showQrImage && qr !== null ? (
              <img className="rc-qr" src={qr} alt={t.sales.ebarimt} />
            ) : null}
            {ebarimt.receipt_id ? (
              <div className="rc-code">
                {t.sales.ebarimtId}: {ebarimt.receipt_id}
              </div>
            ) : null}
            {!showQrImage && qr !== null && qr.trim() !== "" ? (
              <div className="rc-code">{qr}</div>
            ) : null}
            {ebarimt.lottery_no ? (
              <div className="rc-code">
                {t.sales.lotteryNo}: {ebarimt.lottery_no}
              </div>
            ) : null}
            {!ebarimt.receipt_id ? <div className="rc-muted">{ebarimt.status_name}</div> : null}
          </div>
        </>
      ) : null}

      {receipt.note ? (
        <>
          <hr className="rc-rule" />
          <div className="rc-muted">
            {t.common.note}: {receipt.note}
          </div>
        </>
      ) : null}

      <hr className="rc-rule" />
      <div className="rc-center rc-footer">{station.footer}</div>
    </div>
  );
}

export default ReceiptTemplate;
