/**
 * Админ — өдрийн хаалтын бүрэн засварын цонхнууд (``shifts.adjust``).
 *
 * * Тос, бараа — барааг солих, тоо/үнэ засах, мөр нэмэх/хасах;
 * * Зээл — харилцагч солих, түлш (төрөл, литр/дүн, үнэ) ба бараа;
 * * Миль, үнийн тэмдэглэл — үнэ өөрчлөгдсөн ч тэмдэглэлгүй хаасан ээлжид
 *   шинэ үнэ эхэлсэн милийг нөхөх, буруу бичсэн хаалтын милийг засах.
 *
 * Цонх бүр нээгдэх үедээ л mount хийгдэнэ (ClosingWindow) — бараа,
 * харилцагчийн жагсаалтыг дэмий татахгүй.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Fuel, Package, Plus, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useProducts } from "../../api/queries/products";
import {
  useClosingFuelEditor,
  useClosingFuelPreviewMutation,
  useClosingFuels,
  useClosingProductPriceFetcher,
} from "../../api/queries/shifts";
import type {
  ClosingCreditItemInput,
  ClosingFuelInput,
  ClosingPriceHint,
  ClosingTarget,
  ClosingView,
  MoneyStr,
  UUID,
} from "../../api/types";
import { t } from "../../i18n/mn";
import { dCmp, dMul, dSum, dToQty, toDisplay } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMoneyExact, formatQty } from "../../lib/format";
import { FieldLabel, NumberField, PickerField, TextField, useDebounced } from "../../pages/catalog/_shared";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";
import { DialogFooter, T, TargetFields, toTarget, trimQty } from "./closingShared";

type CreditLine = ClosingView["credit_lines"][number];

/** Мөрийн дүн = тоо × нэгж үнэ (2 орон). */
function lineAmount(qty: string, price: string): string {
  if (qty === "" || price === "") return "0.00";
  return dMul(price, dToQty(qty));
}

function Amount({ value }: { value: MoneyStr }) {
  return (
    <div className="flex h-12 items-center justify-end rounded-xl bg-surface-alt px-3 sm:h-14">
      <span className="num text-[15px] font-bold text-ink">{formatMoneyExact(value)}</span>
    </div>
  );
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="md"
      icon={<Trash2 />}
      onClick={onClick}
      aria-label={T.removeLine}
      title={T.removeLine}
      className="text-danger-dark"
    />
  );
}

/** Барааны сонголт — идэвхтэй бараа + мөрөнд байгаа (идэвхгүй болсон ч) бараа. */
function useProductOptions(extra: { id: string; name: string }[]) {
  const { data } = useProducts({ limit: 500, active_only: true });
  return useMemo(() => {
    const out = (data?.items ?? []).map((p) => ({
      value: p.id,
      label: p.name_mn,
      hint: `${p.sku} · ${formatMoneyExact(p.price)} · ${formatQty(p.stock_qty, p.unit)}`,
    }));
    for (const row of extra) {
      if (row.id && !out.some((o) => o.value === row.id)) out.push({ value: row.id, label: row.name, hint: "" });
    }
    return out;
  }, [data, extra]);
}

// --------------------------------------------------------------------------
// Тос, барааны борлуулалт
// --------------------------------------------------------------------------
interface GoodsRow {
  key: number;
  product_id: string;
  qty: string;
  unit_price: string;
}

export function OilLinesDialog({
  shiftId,
  view,
  busy,
  onClose,
  onSave,
}: {
  shiftId: UUID;
  view: ClosingView;
  busy: boolean;
  onClose: () => void;
  onSave: (body: { lines: { product_id: UUID; qty: string; unit_price: MoneyStr | null }[]; note?: string }) => void;
}) {
  const nextKey = useRef(view.oil_lines.length + 1);
  const [rows, setRows] = useState<GoodsRow[]>(() =>
    view.oil_lines.map((line, index) => ({
      key: index + 1,
      product_id: line.product_id ?? "",
      qty: trimQty(line.qty),
      unit_price: toDisplay(line.unit_price),
    })),
  );
  const [note, setNote] = useState("");
  const extra = useMemo(() => view.oil_lines.map((l) => ({ id: l.product_id ?? "", name: l.name })), [view.oil_lines]);
  const productOptions = useProductOptions(extra);
  const priceAt = useClosingProductPriceFetcher(shiftId);

  const update = (key: number, patch: Partial<GoodsRow>) =>
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const pickProduct = (key: number, productId: string) => {
    update(key, { product_id: productId });
    priceAt(productId)
      .then((res) => update(key, { unit_price: toDisplay(res.price) }))
      .catch(() => undefined);
  };
  const total = dSum(rows.map((row) => lineAmount(row.qty, row.unit_price)));
  const serialize = (list: GoodsRow[]) =>
    JSON.stringify(list.map((row) => [row.product_id, Number(row.qty || "0"), Number(row.unit_price || "0")]));
  const [initial] = useState(() => serialize(rows));
  const valid =
    serialize(rows) !== initial &&
    rows.every((row) => row.product_id !== "" && dToQty(row.qty || "0") > 0 && row.unit_price !== "");

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={T.oilTitle}
      footer={
        <DialogFooter
          busy={busy}
          disabled={!valid}
          onClose={onClose}
          onSave={() =>
            onSave({
              lines: rows.map((row) => ({ product_id: row.product_id, qty: row.qty, unit_price: row.unit_price })),
              note,
            })
          }
        />
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{T.oilHint}</p>
        {rows.length === 0 ? (
          <p className="rounded-xl border border-dashed border-warning bg-warning-soft px-3 py-2.5 text-sm text-warning-dark">{T.noLines}</p>
        ) : null}
        {rows.map((row, index) => (
          <div key={row.key} className="flex flex-col gap-3 rounded-xl border border-line px-3 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">
                {T.product} {index + 1}
              </span>
              <RemoveButton onClick={() => setRows((prev) => prev.filter((r) => r.key !== row.key))} />
            </div>
            <PickerField
              label={T.product}
              value={row.product_id}
              options={productOptions}
              onChange={(value) => pickProduct(row.key, value)}
            />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <NumberField name={`oil-qty-${row.key}`} label={T.qty} value={row.qty} onChange={(v) => update(row.key, { qty: v })} maxDecimals={3} />
              <NumberField
                name={`oil-price-${row.key}`}
                label={T.unitPrice}
                value={row.unit_price}
                onChange={(v) => update(row.key, { unit_price: v })}
                suffix={t.units.mnt}
              />
              <div className="col-span-2 flex flex-col gap-1.5 sm:col-span-1">
                <FieldLabel>{T.lineAmount}</FieldLabel>
                <Amount value={lineAmount(row.qty, row.unit_price)} />
              </div>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="secondary"
            size="md"
            icon={<Plus />}
            onClick={() => setRows((prev) => [...prev, { key: nextKey.current++, product_id: "", qty: "1", unit_price: "" }])}
          >
            {T.addProduct}
          </Button>
          <span className="num text-lg font-black text-ink">
            {T.total}: {formatMoneyExact(total)}
          </span>
        </div>
        <TextField label={T.note} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Зээлийн борлуулалт — нэмэх / засах
// --------------------------------------------------------------------------
interface CreditRow {
  key: number;
  kind: "fuel" | "product";
  fuel_id: string;
  price: string;
  mode: "amount" | "liters";
  value: string;
  product_id: string;
  qty: string;
  unit_price: string;
  /** Анхны түлшний мөр — өөрчлөгдөөгүй бол серверт яг хэвээр нь илгээнэ. */
  orig?: { fuel_id: string; price: string; qty: string; amount: string };
}

function rowFromItem(item: CreditLine["items"][number], key: number): CreditRow {
  const base: CreditRow = {
    key,
    kind: item.item_type === "product" ? "product" : "fuel",
    fuel_id: item.fuel_id ?? "",
    price: toDisplay(item.unit_price),
    mode: "amount",
    value: toDisplay(item.amount),
    product_id: item.product_id ?? "",
    qty: trimQty(item.qty),
    unit_price: toDisplay(item.unit_price),
  };
  if (base.kind === "fuel") {
    base.orig = { fuel_id: base.fuel_id, price: base.price, qty: String(item.qty), amount: toDisplay(item.amount) };
  }
  return base;
}

function serializeRow(row: CreditRow): ClosingCreditItemInput {
  if (row.kind === "product") {
    return { product_id: row.product_id, qty: row.qty, unit_price: row.unit_price };
  }
  const o = row.orig;
  const unchanged =
    o !== undefined &&
    row.fuel_id === o.fuel_id &&
    row.price === o.price &&
    row.mode === "amount" &&
    row.value !== "" &&
    dCmp(row.value, o.amount) === 0;
  if (unchanged && o) return { fuel_id: row.fuel_id, unit_price: row.price, qty: o.qty, amount: o.amount };
  return {
    fuel_id: row.fuel_id,
    unit_price: row.price || null,
    ...(row.mode === "amount" ? { amount: row.value } : { qty: row.value }),
  };
}

export function CreditEditDialog({
  shiftId,
  line,
  busy,
  onClose,
  onSave,
}: {
  shiftId: UUID;
  /** Хоосон бол шинэ зээл. */
  line: CreditLine | null;
  busy: boolean;
  onClose: () => void;
  onSave: (body: { sale_id: UUID | null; target: ClosingTarget | null; items: ClosingCreditItemInput[] | null; note?: string }) => void;
}) {
  const fuels = useClosingFuels(shiftId);
  const priceAt = useClosingProductPriceFetcher(shiftId);
  const initialTarget = line?.contract_id ? `c:${line.contract_id}` : line?.customer_id ? `u:${line.customer_id}` : "";
  const [target, setTarget] = useState(initialTarget);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const nextKey = useRef((line?.items.length ?? 0) + 1);
  const [rows, setRows] = useState<CreditRow[]>(() => (line?.items ?? []).map((item, index) => rowFromItem(item, index + 1)));
  const initialItems = useMemo(
    () => JSON.stringify((line?.items ?? []).map((item, index) => serializeRow(rowFromItem(item, index + 1)))),
    [line],
  );
  const extra = useMemo(
    () => (line?.items ?? []).filter((i) => i.item_type === "product").map((i) => ({ id: i.product_id ?? "", name: i.name })),
    [line],
  );
  const productOptions = useProductOptions(extra);

  // Түлшний сонголт — нэгдсэн (бэлэн) борлуулалтад байгаа литр + энэ зээлийн өөрийн мөрүүд.
  const pool = fuels.data ?? [];
  const fuelOptions = useMemo(() => {
    const out = pool.map((f) => ({
      value: f.fuel_id,
      label: f.name,
      hint: `${T.available}: ${formatLiters(f.liters, 2)} · ${formatMoneyExact(f.amount)}`,
    }));
    for (const item of line?.items ?? []) {
      if (item.item_type !== "product" && item.fuel_id && !out.some((o) => o.value === item.fuel_id)) {
        out.push({ value: item.fuel_id, label: item.name, hint: "" });
      }
    }
    return out;
  }, [pool, line]);
  const pricesFor = (row: CreditRow): string[] => {
    const out = (pool.find((f) => f.fuel_id === row.fuel_id)?.prices ?? []).map((p) => toDisplay(p.price));
    if (row.orig && row.orig.fuel_id === row.fuel_id && !out.includes(row.orig.price)) out.push(row.orig.price);
    return out;
  };

  const update = (key: number, patch: Partial<CreditRow>) =>
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const addRow = (kind: "fuel" | "product") =>
    setRows((prev) => [
      ...prev,
      { key: nextKey.current++, kind, fuel_id: "", price: "", mode: "amount", value: "", product_id: "", qty: "1", unit_price: "" },
    ]);
  const pickFuel = (row: CreditRow, fuelId: string) => {
    const prices = (pool.find((f) => f.fuel_id === fuelId)?.prices ?? []).map((p) => toDisplay(p.price));
    update(row.key, { fuel_id: fuelId, price: prices.length === 1 ? prices[0] : "" });
  };
  const pickProduct = (key: number, productId: string) => {
    update(key, { product_id: productId });
    priceAt(productId)
      .then((res) => update(key, { unit_price: toDisplay(res.price) }))
      .catch(() => undefined);
  };

  const rowAmount = (row: CreditRow): string => {
    if (row.kind === "product") return lineAmount(row.qty, row.unit_price);
    if (row.mode === "amount") return row.value === "" ? "0.00" : toDisplay(row.value);
    return lineAmount(row.value, row.price);
  };
  const total = dSum(rows.map(rowAmount));
  const rowValid = (row: CreditRow): boolean =>
    row.kind === "product"
      ? row.product_id !== "" && dToQty(row.qty || "0") > 0 && row.unit_price !== ""
      : row.fuel_id !== "" && dToQty(row.value || "0") > 0 && (pricesFor(row).length <= 1 || row.price !== "");
  const resolved = toTarget(target, name, phone);
  const items = rows.map(serializeRow);
  const itemsChanged = !line || JSON.stringify(items) !== initialItems;
  const targetChanged = !line || target !== initialTarget;
  const valid = rows.length > 0 && rows.every(rowValid) && (targetChanged ? resolved !== null : true) && (itemsChanged || targetChanged);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={line ? T.creditEditTitle : T.creditAddTitle}
      subtitle={line ? `№${line.number} · ${line.customer}` : undefined}
      footer={
        <DialogFooter
          busy={busy}
          disabled={!valid}
          onClose={onClose}
          onSave={() =>
            onSave({
              sale_id: line?.sale_id ?? null,
              target: targetChanged ? resolved : null,
              items: itemsChanged ? items : null,
              note,
            })
          }
        />
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{T.creditEditHint}</p>
        <TargetFields
          value={target}
          onChange={setTarget}
          name={name}
          onName={setName}
          phone={phone}
          onPhone={setPhone}
          enabled
          placeholder={line ? [line.customer, line.contract_no].filter(Boolean).join(" · ") : undefined}
        />
        {rows.map((row) => {
          const prices = row.kind === "fuel" ? pricesFor(row) : [];
          return (
            <div key={row.key} className="flex flex-col gap-3 rounded-xl border border-line px-3 py-3">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-xs font-bold tracking-wide text-ink-soft uppercase">
                  {row.kind === "fuel" ? <Fuel className="h-4 w-4" /> : <Package className="h-4 w-4" />}
                  {row.kind === "fuel" ? T.fuelLine : T.productLine}
                </span>
                <span className="flex items-center gap-2">
                  <span className="num font-bold text-ink">{formatMoneyExact(rowAmount(row))}</span>
                  <RemoveButton onClick={() => setRows((prev) => prev.filter((r) => r.key !== row.key))} />
                </span>
              </div>
              {row.kind === "fuel" ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <PickerField label={T.fuel} value={row.fuel_id} options={fuelOptions} onChange={(v) => pickFuel(row, v)} searchable={false} />
                  {prices.length > 1 ? (
                    <PickerField
                      label={T.takenAtPrice}
                      value={row.price}
                      options={prices.map((p) => ({ value: p, label: formatMoneyExact(p) }))}
                      onChange={(v) => update(row.key, { price: v })}
                      searchable={false}
                    />
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      <FieldLabel>{T.unitPrice}</FieldLabel>
                      <Amount value={row.price || prices[0] || "0"} />
                    </div>
                  )}
                  <PickerField
                    label={T.entryMode}
                    value={row.mode}
                    options={[
                      { value: "amount", label: T.byAmount },
                      { value: "liters", label: T.byLiters },
                    ]}
                    onChange={(v) => update(row.key, { mode: v as "amount" | "liters", value: "" })}
                    searchable={false}
                  />
                  <NumberField
                    name={`credit-value-${row.key}`}
                    label={row.mode === "amount" ? T.pumpAmount : T.liters}
                    value={row.value}
                    onChange={(v) => update(row.key, { value: v })}
                    suffix={row.mode === "amount" ? t.units.mnt : t.units.liter}
                    maxDecimals={row.mode === "amount" ? 2 : 3}
                  />
                </div>
              ) : (
                <>
                  <PickerField
                    label={T.product}
                    value={row.product_id}
                    options={productOptions}
                    onChange={(v) => pickProduct(row.key, v)}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <NumberField name={`credit-qty-${row.key}`} label={T.qty} value={row.qty} onChange={(v) => update(row.key, { qty: v })} maxDecimals={3} />
                    <NumberField
                      name={`credit-price-${row.key}`}
                      label={T.unitPrice}
                      value={row.unit_price}
                      onChange={(v) => update(row.key, { unit_price: v })}
                      suffix={t.units.mnt}
                    />
                  </div>
                </>
              )}
            </div>
          );
        })}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="flex flex-wrap gap-2">
            <Button variant="secondary" size="md" icon={<Fuel />} onClick={() => addRow("fuel")}>
              {T.addFuel}
            </Button>
            <Button variant="secondary" size="md" icon={<Package />} onClick={() => addRow("product")}>
              {T.addProduct}
            </Button>
          </span>
          <span className="num text-lg font-black text-ink">
            {T.total}: {formatMoneyExact(total)}
          </span>
        </div>
        <TextField label={T.note} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Үнийн сануулга
// --------------------------------------------------------------------------
export function PriceHintList({ hints }: { hints: ClosingPriceHint[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {hints.map((hint) => (
        <li key={`${hint.fuel_id}-${hint.applied_at}`} className="num text-sm">
          {T.priceHintBody
            .replace("{fuel}", hint.fuel_name)
            .replace("{old}", formatMoneyExact(hint.old_price))
            .replace("{new}", formatMoneyExact(hint.new_price))
            .replace("{at}", formatDateTime(hint.applied_at))
            .replace("{nozzles}", hint.nozzles.map((n) => n.label).join(", "))}
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Хаалтын миль ба үнийн тэмдэглэл
// --------------------------------------------------------------------------
interface MarkRow {
  key: number;
  reading: string;
  new_price: string;
}

const num = (value: string): number => (value === "" ? Number.NaN : Number(value));
const sameReading = (a: string, b: string): boolean => Number(a).toFixed(3) === Number(b).toFixed(3);
const markKey = (nozzleId: string, reading: string, price: string): string =>
  `${nozzleId}|${Number(reading).toFixed(3)}|${Number(price).toFixed(2)}`;

function OldNew({ label, old, value, strong }: { label: string; old: MoneyStr; value: MoneyStr; strong?: boolean }) {
  const changed = dCmp(old, value) !== 0;
  return (
    <div className="num flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-1 text-[15px]">
      <span className={strong ? "font-bold text-ink" : "text-ink-soft"}>{label}</span>
      <span className="flex items-baseline gap-2">
        {changed ? <span className="text-sm text-ink-faint line-through">{formatMoneyExact(old)}</span> : null}
        <span className={`${strong ? "font-black" : "font-semibold"} ${changed ? "text-action" : "text-ink"}`}>{formatMoneyExact(value)}</span>
      </span>
    </div>
  );
}

export function FuelEditorDialog({
  shiftId,
  busy,
  onClose,
  onSave,
}: {
  shiftId: UUID;
  busy: boolean;
  onClose: () => void;
  onSave: (input: ClosingFuelInput) => void;
}) {
  const editor = useClosingFuelEditor(shiftId);
  const preview = useClosingFuelPreviewMutation(shiftId);
  const data = editor.data;
  const nextKey = useRef(1);
  const [closes, setCloses] = useState<Record<string, string>>({});
  const [marks, setMarks] = useState<Record<string, MarkRow[]>>({});
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [ready, setReady] = useState(false);

  if (data && !ready) {
    setReady(true);
    setCloses(Object.fromEntries(data.nozzles.map((n) => [n.nozzle_id, String(n.close_reading)])));
    setMarks(
      Object.fromEntries(
        data.nozzles.map((n) => [
          n.nozzle_id,
          n.marks.map((m) => ({ key: nextKey.current++, reading: String(m.reading), new_price: toDisplay(m.new_price) })),
        ]),
      ),
    );
  }

  const initialMarks = useMemo(
    () =>
      (data?.nozzles ?? [])
        .flatMap((n) => n.marks.map((m) => markKey(n.nozzle_id, String(m.reading), String(m.new_price))))
        .sort()
        .join(";"),
    [data],
  );

  // Шалгалт — миль нээлт ба хаалтын хооронд, үнэ эерэг.
  const invalid = useMemo(() => {
    if (!data || !ready) return true;
    for (const n of data.nozzles) {
      const open = Number(n.open_reading);
      const close = num(closes[n.nozzle_id] ?? "");
      if (!(close >= open)) return true;
      for (const m of marks[n.nozzle_id] ?? []) {
        const reading = num(m.reading);
        if (!(reading >= open && reading <= close) || !(num(m.new_price) > 0)) return true;
      }
    }
    return false;
  }, [data, ready, closes, marks]);

  const input = useMemo<ClosingFuelInput | null>(() => {
    if (!data || invalid) return null;
    return {
      readings: data.nozzles
        .filter((n) => !sameReading(closes[n.nozzle_id] ?? "", String(n.close_reading)))
        .map((n) => ({ nozzle_id: n.nozzle_id, reading: closes[n.nozzle_id] })),
      marks: data.nozzles.flatMap((n) =>
        (marks[n.nozzle_id] ?? []).map((m) => ({ nozzle_id: n.nozzle_id, reading: m.reading, new_price: m.new_price })),
      ),
      credit_prices: Object.entries(prices).map(([item_id, unit_price]) => ({ item_id, unit_price })),
    };
  }, [data, invalid, closes, marks, prices]);

  const marksNow = (input?.marks ?? [])
    .map((m) => markKey(m.nozzle_id, m.reading, m.new_price))
    .sort()
    .join(";");
  const changed =
    input !== null && ((input.readings?.length ?? 0) > 0 || (input.credit_prices?.length ?? 0) > 0 || marksNow !== initialMarks);

  // Урьдчилсан тооцоо — оролт өөрчлөгдөх бүрд (бага зэрэг хүлээгээд).
  const inputKey = input && changed ? JSON.stringify(input) : "";
  const debouncedKey = useDebounced(inputKey, 450);
  const runPreview = preview.mutate;
  useEffect(() => {
    if (debouncedKey) runPreview(JSON.parse(debouncedKey) as ClosingFuelInput);
  }, [debouncedKey, runPreview]);
  const fresh = Boolean(inputKey) && JSON.stringify(preview.variables ?? null) === inputKey && preview.isSuccess;
  const result = fresh ? preview.data : undefined;
  const previewNozzles = new Map((result?.nozzles ?? []).map((n) => [n.nozzle_id, n]));

  const addMark = (nozzleId: string, price = "") =>
    setMarks((prev) => ({ ...prev, [nozzleId]: [...(prev[nozzleId] ?? []), { key: nextKey.current++, reading: "", new_price: price }] }));
  const updateMark = (nozzleId: string, key: number, patch: Partial<MarkRow>) =>
    setMarks((prev) => ({ ...prev, [nozzleId]: (prev[nozzleId] ?? []).map((m) => (m.key === key ? { ...m, ...patch } : m)) }));
  const removeMark = (nozzleId: string, key: number) =>
    setMarks((prev) => ({ ...prev, [nozzleId]: (prev[nozzleId] ?? []).filter((m) => m.key !== key) }));
  // Сануулгын хошуу бүрд шинэ үнээр хоосон тэмдэглэл бэлдэнэ (милийг админ оруулна).
  const prepareHints = () => {
    for (const hint of data?.hints ?? []) {
      for (const nozzle of hint.nozzles) {
        const exists = (marks[nozzle.nozzle_id] ?? []).some((m) => num(m.new_price) === Number(hint.new_price));
        if (!exists) addMark(nozzle.nozzle_id, toDisplay(hint.new_price));
      }
    }
  };

  const errors = result?.errors ?? [];
  const canSave = changed && !invalid && fresh && errors.length === 0 && !preview.isPending;

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={T.fuelTitle}
      footer={<DialogFooter busy={busy} disabled={!canSave} onClose={onClose} onSave={() => input && onSave({ ...input, note: note || null })} />}
    >
      {!data ? (
        <div className="flex justify-center py-10">
          <Spinner label={t.common.loading} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-soft">{T.fuelHint}</p>
          {data.hints.length > 0 ? (
            <div className="flex flex-col gap-2 rounded-xl border-2 border-warning bg-warning-soft px-3 py-2.5 text-warning-dark">
              <span className="flex items-center gap-2 font-bold">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                {T.priceHintTitle}
              </span>
              <PriceHintList hints={data.hints} />
              <div>
                <Button variant="warning" size="sm" icon={<Plus />} onClick={prepareHints}>
                  {T.priceHintFix}
                </Button>
              </div>
            </div>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-2">
            {data.nozzles.map((n) => {
              const close = closes[n.nozzle_id] ?? "";
              const nextGap = n.next_open !== null && close !== "" ? Number(n.next_open) - Number(close) : null;
              const pn = previewNozzles.get(n.nozzle_id);
              const segments = pn?.segments ?? n.segments;
              return (
                <div key={n.nozzle_id} className="flex flex-col gap-3 rounded-xl border border-line px-3 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <span className="font-bold text-ink">{n.label}</span>
                    <span className="text-sm text-ink-soft">
                      {n.fuel_name} · {n.tank_name}
                    </span>
                  </div>
                  <div className="num flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft">
                    <span>
                      {T.openReading}: <b className="text-ink">{formatLiters(n.open_reading, 3)}</b>
                    </span>
                    <span>
                      {T.openPrice}: <b className="text-ink">{formatMoneyExact(n.open_price)}</b>
                    </span>
                  </div>
                  <NumberField
                    name={`fuel-close-${n.nozzle_id}`}
                    label={T.closeReading}
                    value={close}
                    onChange={(v) => setCloses((prev) => ({ ...prev, [n.nozzle_id]: v }))}
                    maxDecimals={3}
                    disabled={n.locked}
                    hint={
                      n.locked
                        ? T.lockedNozzle
                        : n.next_open !== null
                          ? `${T.nextOpen}: ${formatLiters(n.next_open, 3)}${
                              nextGap !== null && Math.abs(nextGap) >= 0.0005
                                ? ` · ${T.nextGap.replace("{gap}", `${nextGap > 0 ? "+" : ""}${formatLiters(nextGap.toFixed(3), 3)}`)}`
                                : ""
                            }`
                          : undefined
                    }
                  />
                  <div className="flex flex-col gap-2">
                    <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">{T.marks}</span>
                    {(marks[n.nozzle_id] ?? []).length === 0 ? <span className="text-sm text-ink-faint">{T.noMarks}</span> : null}
                    {(marks[n.nozzle_id] ?? []).map((m) => {
                      const reading = num(m.reading);
                      const outOfRange =
                        m.reading !== "" && !(reading >= Number(n.open_reading) && reading <= num(close));
                      return (
                        <div key={m.key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end gap-2">
                          <NumberField
                            name={`mark-reading-${m.key}`}
                            label={T.markReading}
                            value={m.reading}
                            onChange={(v) => updateMark(n.nozzle_id, m.key, { reading: v })}
                            maxDecimals={3}
                            hint={
                              outOfRange ? (
                                <span className="text-danger-dark">
                                  {T.markRange
                                    .replace("{open}", formatLiters(n.open_reading, 3))
                                    .replace("{close}", formatLiters(close || "0", 3))}
                                </span>
                              ) : undefined
                            }
                          />
                          <NumberField
                            name={`mark-price-${m.key}`}
                            label={T.newPrice}
                            value={m.new_price}
                            onChange={(v) => updateMark(n.nozzle_id, m.key, { new_price: v })}
                            suffix={t.units.mnt}
                          />
                          <RemoveButton onClick={() => removeMark(n.nozzle_id, m.key)} />
                        </div>
                      );
                    })}
                    <div>
                      <Button variant="secondary" size="sm" icon={<Plus />} onClick={() => addMark(n.nozzle_id)}>
                        {T.addMark}
                      </Button>
                    </div>
                  </div>
                  {segments.length > 0 ? (
                    <div className="num flex flex-col gap-0.5 rounded-lg bg-surface-alt px-2.5 py-2 text-sm text-ink-soft">
                      {segments.map((s, index) => (
                        <span key={index}>
                          {formatLiters(s.liters, 3)} × {formatMoneyExact(s.price)} = <b className="text-ink">{formatMoneyExact(s.amount)}</b>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* Үр дүн */}
          <div className="flex flex-col gap-2 rounded-xl border-2 border-line-strong px-3 py-3">
            <span className="flex items-center gap-2 font-bold text-ink">
              {T.preview}
              {preview.isPending ? <Spinner size="sm" /> : null}
            </span>
            {!changed ? (
              <span className="text-sm text-ink-faint">{T.noChange}</span>
            ) : preview.isError && !preview.isPending ? (
              <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger-dark">{errorMessage(preview.error)}</p>
            ) : result ? (
              <>
                <OldNew label={T.fuelByMile} old={result.fuel_total.old} value={result.fuel_total.new} />
                <OldNew label={T.fuelSaleRow} old={result.fuel_sale_total.old} value={result.fuel_sale_total.new} />
                <OldNew label={T.creditRow} old={result.credit_total.old} value={result.credit_total.new} />
                <OldNew label={T.mustRow} old={result.must.old} value={result.must.new} strong />
                <OldNew label={T.diffRow} old={result.diff.old} value={result.diff.new} strong />
                {result.tanks.map((tank) => (
                  <span key={tank.tank_id} className="num text-sm text-ink-soft">
                    {T.tankRow}:{" "}
                    {(Number(tank.liters) > 0 ? T.tankOut : T.tankIn)
                      .replace("{tank}", tank.name)
                      .replace("{liters}", formatLiters(Math.abs(Number(tank.liters)).toFixed(3), 3))}
                  </span>
                ))}
                {result.credit_items.some((c) => c.prices.length > 1 || !c.ok) ? (
                  <div className="mt-1 flex flex-col gap-2 border-t border-line pt-2">
                    <span className="font-semibold text-ink">{T.creditPrices}</span>
                    <span className="text-xs text-ink-soft">{T.creditPricesHint}</span>
                    {result.credit_items
                      .filter((c) => c.prices.length > 1 || !c.ok)
                      .map((c) => {
                        const options = [...c.prices.map((p) => toDisplay(p))];
                        if (!options.includes(toDisplay(c.old_price))) options.push(toDisplay(c.old_price));
                        return (
                          <div key={c.item_id} className="grid items-end gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,16rem)]">
                            <span className={`num text-sm ${c.ok ? "text-ink" : "font-semibold text-danger-dark"}`}>
                              №{c.number} · {c.customer} · {c.fuel_name} {formatLiters(c.liters, 3)} → {formatMoneyExact(c.amount)}
                            </span>
                            <PickerField
                              label={T.takenAtPrice}
                              value={prices[c.item_id] ?? toDisplay(c.price)}
                              options={options.map((p) => ({ value: p, label: formatMoneyExact(p) }))}
                              onChange={(v) =>
                                setPrices((prev) => {
                                  const next = { ...prev };
                                  if (dCmp(v, c.old_price) === 0) delete next[c.item_id];
                                  else next[c.item_id] = v;
                                  return next;
                                })
                              }
                              searchable={false}
                            />
                          </div>
                        );
                      })}
                  </div>
                ) : null}
                {errors.length > 0 ? (
                  <div className="flex flex-col gap-1 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger-dark">
                    <span className="font-bold">{T.errorsTitle}</span>
                    {errors.map((e, index) => (
                      <span key={index}>{e}</span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <span className="text-sm text-ink-faint">{T.previewing}</span>
            )}
          </div>
          <TextField label={T.note} value={note} onChange={setNote} />
        </div>
      )}
    </Modal>
  );
}
