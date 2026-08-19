/**
 * Түгээгчийн бүртгэл — оруулсан тоо ба дарсан зураг хажуу хажууд.
 *
 * Ээлж хаагдсаны дараа маргаан гарвал "хэдийг бичсэн бэ" гэдгийг зөвхөн
 * тоогоор шалгаад ашиггүй: тоолуурын зураг л баримт болно. Иймд тоо болон
 * түүнд харгалзах зургийг ЗААВАЛ хамт харуулна — нэг нь дутуу бол тэр нь
 * шууд харагдана.
 *
 * Зургийг `<img src>`-ээр шууд татаж чадахгүй (эндпойнт Bearer токен
 * шаарддаг, img толгой явуулдаггүй) тул блоб болгож ачаална.
 */

import { useEffect, useState } from "react";
import { Camera, ImageOff, ZoomIn } from "lucide-react";

import { blobUrl } from "../../api/client";
import { usePriceMarks, useShiftAttachments } from "../../api/queries/shifts";
import type { ShiftAttachment, ShiftNozzleRow, ShiftReport, UUID } from "../../api/types";
import { Card } from "../ui/Card";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";
import { t } from "../../i18n/mn";
import { dIsPositive, dIsZero } from "../../lib/decimal";
import { formatDateTime, formatMNT, formatNumber } from "../../lib/format";

interface RecordItem {
  key: string;
  group: string;
  label: string;
  value: string;
  /** Тайлбар мөр — милийн зөрүү гэх мэт. */
  hint?: string;
  /** Анхааруулга өнгөтэй эсэх. */
  warn?: boolean;
  photos: ShiftAttachment[];
}

// --------------------------------------------------------------------------
// Нэг зураг — токентой татаж, блоб URL болгоно
// --------------------------------------------------------------------------
function Thumb({
  shiftId,
  attachment,
  onOpen,
}: {
  shiftId: UUID;
  attachment: ShiftAttachment;
  onOpen: (url: string, attachment: ShiftAttachment) => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let dropped = false;
    let created: string | null = null;
    blobUrl("/api/shifts/" + shiftId + "/attachments/" + attachment.id + "/file")
      .then((value) => {
        // Компонент аль хэдийн салсан бол блобыг шууд чөлөөлнө — эс бөгөөс
        // хуудас хаагдтал санах ойд үлдэнэ.
        if (dropped) {
          URL.revokeObjectURL(value);
          return;
        }
        created = value;
        setUrl(value);
      })
      .catch(() => {
        if (!dropped) setFailed(true);
      });
    return () => {
      dropped = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [shiftId, attachment.id]);

  if (failed) {
    return (
      <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-alt text-ink-faint">
        <ImageOff className="h-5 w-5" />
      </div>
    );
  }
  if (!url) {
    return (
      <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-alt">
        <Spinner size="sm" />
      </div>
    );
  }
  if (attachment.content_type === "application/pdf") {
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="flex h-20 w-20 shrink-0 flex-col items-center justify-center gap-1 rounded-lg border border-line bg-surface-alt text-xs font-semibold text-ink-soft hover:bg-surface-sunken"
      >
        <Camera className="h-5 w-5" />
        PDF
      </a>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(url, attachment)}
      title={t.attendant.openPhoto}
      className="group relative h-20 w-20 shrink-0 overflow-hidden rounded-lg border border-line bg-surface-alt"
    >
      <img src={url} alt={attachment.original_name} className="h-full w-full object-cover" />
      <span className="absolute inset-0 flex items-center justify-center text-white opacity-0 transition group-hover:bg-brand-950/40 group-hover:opacity-100">
        <ZoomIn className="h-5 w-5" />
      </span>
    </button>
  );
}

// --------------------------------------------------------------------------
// Бүртгэлийн нэг мөр — тоо зүүн талд, зураг баруун талд
// --------------------------------------------------------------------------
function Row({
  shiftId,
  item,
  onOpen,
}: {
  shiftId: UUID;
  item: RecordItem;
  onOpen: (url: string, attachment: ShiftAttachment) => void;
}) {
  return (
    <div
      className={[
        "flex items-center gap-4 rounded-xl border px-3.5 py-3",
        item.warn ? "border-warning bg-warning-soft/40" : "border-line bg-white",
      ].join(" ")}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink">{item.label}</p>
        <p className="num text-lg font-black text-ink">{item.value}</p>
        {item.hint ? (
          <p
            className={
              item.warn
                ? "num text-xs font-semibold text-warning-dark"
                : "num text-xs font-semibold text-ink-soft"
            }
          >
            {item.hint}
          </p>
        ) : null}
      </div>
      {item.photos.length > 0 ? (
        <div className="flex shrink-0 gap-2">
          {item.photos.map((photo) => (
            <Thumb key={photo.id} shiftId={shiftId} attachment={photo} onOpen={onOpen} />
          ))}
        </div>
      ) : (
        <div className="flex h-20 w-20 shrink-0 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-line px-1 text-center text-[11px] font-semibold text-ink-faint">
          <ImageOff className="h-4 w-4" />
          {t.attendant.noPhoto}
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
export function AttendantRecord({ shiftId, report }: { shiftId: UUID; report: ShiftReport }) {
  const { data: attachments } = useShiftAttachments(shiftId);
  const { data: marks } = usePriceMarks(shiftId);
  const [viewing, setViewing] = useState<{ url: string; attachment: ShiftAttachment } | null>(null);

  const files = attachments ?? [];
  const priceMarks = marks ?? [];
  const byKind = (kind: string, refId: UUID | null): ShiftAttachment[] =>
    files.filter((f) => f.kind === kind && (refId === null ? f.ref_id === null : f.ref_id === refId));

  const nozzleLabel = (row: ShiftNozzleRow): string =>
    row.pump_name + " · №" + row.nozzle_number + " " + row.fuel_name;

  const items: RecordItem[] = [];

  // --- Нээлт: эхний бэлэн мөнгө + хошуу бүрийн миль ---
  items.push({
    key: "open-cash",
    group: t.attendant.photoOpen,
    label: t.attendant.photoCash,
    value: formatMNT(report.cash.opening_cash),
    photos: byKind("open", null),
  });
  for (const row of report.nozzles) {
    if (row.opening_reading === null) continue;
    const gap = row.mile_gap_l;
    const hasGap = gap !== null && !dIsZero(gap);
    let hint: string | undefined;
    if (row.prev_close_reading !== null) {
      const head = t.attendant.prevClose + " " + formatNumber(row.prev_close_reading, 3);
      hint = hasGap
        ? head +
          " · " +
          t.attendant.mileGap +
          " " +
          (dIsPositive(gap ?? "0") ? "+" : "") +
          formatNumber(gap ?? "0", 3) +
          " " +
          t.units.liter
        : head + " · " + t.attendant.mileMatches;
    }
    items.push({
      key: "open-" + row.nozzle_id,
      group: t.attendant.photoOpen,
      label: nozzleLabel(row) + " — " + t.attendant.openMile,
      value: formatNumber(row.opening_reading, 3) + " " + t.units.liter,
      hint,
      warn: hasGap,
      photos: byKind("open", row.nozzle_id),
    });
  }

  // --- Хаалт: хошуу бүрийн эцсийн миль ---
  for (const row of report.nozzles) {
    if (row.closing_reading === null) continue;
    items.push({
      key: "close-" + row.nozzle_id,
      group: t.attendant.photoClose,
      label: nozzleLabel(row) + " — " + t.attendant.closeMile,
      value: formatNumber(row.closing_reading, 3) + " " + t.units.liter,
      hint:
        row.reading_delta_l === null
          ? undefined
          : t.pos.liters + " " + formatNumber(row.reading_delta_l, 3) + " " + t.units.liter,
      photos: byKind("close", row.nozzle_id),
    });
  }

  // --- Settlement (банкны терминалын тооцоо) ---
  const settlementPhotos = files.filter((f) => f.kind === "settlement");
  if (report.daily || settlementPhotos.length > 0) {
    items.push({
      key: "settlement",
      group: t.attendant.photoSettlement,
      label: t.attendant.settlementTotal,
      value: formatMNT(report.daily?.settlement_total ?? "0"),
      photos: settlementPhotos,
    });
  }

  // --- Үнийн тэмдэглэл ---
  const markPhotos = files.filter((f) => f.kind === "price_mark");
  priceMarks.forEach((mark, index) => {
    items.push({
      key: "mark-" + mark.id,
      group: t.attendant.photoPriceMark,
      label: "№" + (mark.nozzle_number ?? "—") + " " + mark.fuel_name + " — " + t.attendant.markReading,
      value: formatNumber(mark.reading, 3) + " " + t.units.liter,
      hint:
        formatMNT(mark.old_price) +
        " → " +
        formatMNT(mark.new_price) +
        (mark.note ? " · " + mark.note : ""),
      // Үнийн тэмдэглэлийн зураг хошуутай холбогддоггүй тул эхний мөрөнд бүгдийг.
      photos: index === 0 ? markPhotos : [],
    });
  });

  if (items.length === 0) return null;

  const groups = [...new Set(items.map((item) => item.group))];

  return (
    <Card title={t.attendant.attendantRecord} subtitle={t.attendant.attendantRecordHint}>
      <div className="flex flex-col gap-5">
        {groups.map((group) => (
          <div key={group} className="flex flex-col gap-2">
            <p className="text-xs font-bold tracking-wide text-ink-faint uppercase">{group}</p>
            <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
              {items
                .filter((item) => item.group === group)
                .map((item) => (
                  <Row
                    key={item.key}
                    shiftId={shiftId}
                    item={item}
                    onOpen={(url, attachment) => setViewing({ url, attachment })}
                  />
                ))}
            </div>
          </div>
        ))}
      </div>

      <Modal
        open={viewing !== null}
        onClose={() => setViewing(null)}
        size="xl"
        title={viewing?.attachment.original_name}
        subtitle={viewing ? formatDateTime(viewing.attachment.created_at) : undefined}
      >
        {viewing ? (
          <img
            src={viewing.url}
            alt={viewing.attachment.original_name}
            className="mx-auto max-h-[70vh] w-auto rounded-xl"
          />
        ) : null}
      </Modal>
    </Card>
  );
}

export default AttendantRecord;
