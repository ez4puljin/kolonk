import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Droplets, Package, Plus, Save, Trash2, Truck } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import { useFuels } from "../../api/queries/fuels";
import { useSuppliers } from "../../api/queries/procurement";
import { useProducts } from "../../api/queries/products";
import { useCreateShipmentMutation } from "../../api/queries/shipments";
import { useTanks } from "../../api/queries/tanks";
import type { FuelShipmentCreate } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { t } from "../../i18n/mn";
import { formatLiters, formatMNT, formatNumber, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, FieldLabel, NumberField, PickerField, TextAreaField, TextField } from "../catalog/_shared";

const VAT_RATE = 0.1;

/**
 * Шинэ ачилт — нэг машин, ОЛОН нийлүүлэгч, түлш + бараа, салбар бүрд хуваарилалт.
 *
 * Мөр бүр өөрийн нийлүүлэгчтэй (хоосон бол үндсэн нийлүүлэгч — тээврийн
 * зардал түүнд); бүртгэхэд нийлүүлэгч тус бүрд тусдаа өглөг үүснэ. Мөр
 * бүрийн доор хуваарилалт: түлш → аль салбарын аль саванд хэдэн литр,
 * бараа → аль салбарт хэдэн ширхэг. Бүртгэхэд төлөвлөгөө тэр дороо
 * буулгагдана; хуваарилаагүй үлдэгдлийг дараа нь detail хуудаснаас.
 */
interface FuelAllocDraft {
  key: number;
  tank_id: string;
  liters: string;
}

interface GoodsAllocDraft {
  key: number;
  branch_id: string;
  qty: string;
}

interface ItemDraft {
  key: number;
  fuel_id: string;
  supplier_id: string;
  liters: string;
  unit_cost: string;
  allocations: FuelAllocDraft[];
}

interface GoodsDraft {
  key: number;
  product_id: string;
  supplier_id: string;
  qty: string;
  unit_cost: string;
  allocations: GoodsAllocDraft[];
}

let seq = 0;
const nextKey = (): number => ++seq;
const newItem = (): ItemDraft => ({ key: nextKey(), fuel_id: "", supplier_id: "", liters: "", unit_cost: "", allocations: [] });
const newGoods = (): GoodsDraft => ({ key: nextKey(), product_id: "", supplier_id: "", qty: "", unit_cost: "", allocations: [] });
const newFuelAlloc = (): FuelAllocDraft => ({ key: nextKey(), tank_id: "", liters: "" });
const newGoodsAlloc = (): GoodsAllocDraft => ({ key: nextKey(), branch_id: "", qty: "" });

const num = (value: string): number => Number(value) || 0;
const sum = (values: number[]): number => values.reduce((acc, v) => acc + v, 0);

export function FuelShipmentFormPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  /** Тээврийн зардлыг нэхэмжлэх нийлүүлэгч — тээвэртэй үед л сонгоно. */
  const [freightSupplierId, setFreightSupplierId] = useState("");
  const [vehicleNo, setVehicleNo] = useState("");
  const [driverName, setDriverName] = useState("");
  const [shipmentDate, setShipmentDate] = useState(todayInput());
  const [invoiceNo, setInvoiceNo] = useState("");
  const [freight, setFreight] = useState("");
  const [note, setNote] = useState("");
  const [items, setItems] = useState<ItemDraft[]>([newItem()]);
  const [goods, setGoods] = useState<GoodsDraft[]>([]);

  const suppliersQuery = useSuppliers({ limit: 200, active_only: true });
  const fuelsQuery = useFuels();
  const productsQuery = useProducts({ active_only: true, limit: 500 });
  const tanksQuery = useTanks({ active_only: true });
  const branchesQuery = useBranches();
  const createMutation = useCreateShipmentMutation();

  const suppliers = useMemo(() => suppliersQuery.data?.items ?? [], [suppliersQuery.data]);
  const supplierName = (id: string): string => suppliers.find((s) => s.id === id)?.name ?? "";
  const supplierOptions = useMemo(
    () => suppliers.map((s) => ({ value: s.id, label: s.name, hint: s.register_no ?? undefined })),
    [suppliers],
  );
  // «Үндсэн нийлүүлэгч» гэсэн ойлголт хэрэглэгчид харагдахгүй — мөр бүр өөрийн
  // нийлүүлэгчтэй. Сервер талын supplier_id-д эхний мөрийн (эсвэл тээврийн)
  // нийлүүлэгч очно.
  const lineSupplierOptions = supplierOptions;

  const fuels = useMemo(() => fuelsQuery.data?.items ?? [], [fuelsQuery.data]);
  const fuelOptions = useMemo(
    () => fuels.filter((f) => f.is_active).map((f) => ({ value: f.id, label: f.name_mn })),
    [fuels],
  );
  const products = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data]);
  const productOptions = useMemo(
    () => products.map((p) => ({ value: p.id, label: p.name_mn, hint: `${p.sku} · ${p.unit}` })),
    [products],
  );
  const tanks = useMemo(() => tanksQuery.data?.items ?? [], [tanksQuery.data]);
  const branches = useMemo(() => (branchesQuery.data ?? []).filter((b) => b.is_active), [branchesQuery.data]);
  const branchOptions = useMemo(() => branches.map((b) => ({ value: b.id, label: b.name, hint: b.code })), [branches]);

  const tankOptionsFor = (fuelId: string) =>
    tanks
      .filter((tank) => tank.fuel_id === fuelId)
      .map((tank) => ({
        value: tank.id,
        label: `${tank.branch_name ? `${tank.branch_name} · ` : ""}${tank.name}`,
        hint: `${formatLiters(tank.current_l, 0)} / ${formatLiters(tank.capacity_l, 0)}`,
      }));

  // ------------------------------------------------------------ мөр засах
  const patchItem = (key: number, patch: Partial<ItemDraft>): void =>
    setItems((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const patchGoods = (key: number, patch: Partial<GoodsDraft>): void =>
    setGoods((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const patchFuelAlloc = (itemKey: number, allocKey: number, patch: Partial<FuelAllocDraft>): void =>
    setItems((prev) =>
      prev.map((row) =>
        row.key === itemKey
          ? { ...row, allocations: row.allocations.map((a) => (a.key === allocKey ? { ...a, ...patch } : a)) }
          : row,
      ),
    );
  const patchGoodsAlloc = (goodsKey: number, allocKey: number, patch: Partial<GoodsAllocDraft>): void =>
    setGoods((prev) =>
      prev.map((row) =>
        row.key === goodsKey
          ? { ...row, allocations: row.allocations.map((a) => (a.key === allocKey ? { ...a, ...patch } : a)) }
          : row,
      ),
    );

  // ------------------------------------------------------------ тооцоо
  const validItems = items.filter((row) => row.fuel_id && num(row.liters) > 0 && num(row.unit_cost) >= 0);
  const validGoods = goods.filter((row) => row.product_id && num(row.qty) > 0 && num(row.unit_cost) >= 0);
  const duplicateFuel = new Set(validItems.map((r) => r.fuel_id)).size !== validItems.length;
  const duplicateProduct = new Set(validGoods.map((r) => r.product_id)).size !== validGoods.length;

  const allocatedLiters = (row: ItemDraft): number => sum(row.allocations.map((a) => (a.tank_id ? num(a.liters) : 0)));
  const allocatedQty = (row: GoodsDraft): number => sum(row.allocations.map((a) => (a.branch_id ? num(a.qty) : 0)));
  const overAllocated =
    items.some((row) => allocatedLiters(row) > num(row.liters) + 0.0005) ||
    goods.some((row) => allocatedQty(row) > num(row.qty) + 0.0005);

  /** Серверийн «үндсэн» нийлүүлэгч: тээвэртэй бол тээврийнх, үгүй бол эхний мөрийнх. */
  const firstLineSupplier = validItems[0]?.supplier_id || validGoods[0]?.supplier_id || "";
  const headSupplierId = num(freight) > 0 && freightSupplierId ? freightSupplierId : firstLineSupplier;

  const totals = useMemo(() => {
    const perSupplier = new Map<string, { name: string; subtotal: number }>();
    const bump = (sid: string, amount: number): void => {
      if (!sid) return;
      const entry = perSupplier.get(sid) ?? { name: supplierName(sid), subtotal: 0 };
      entry.subtotal += amount;
      perSupplier.set(sid, entry);
    };
    for (const row of items) bump(row.supplier_id, num(row.liters) * num(row.unit_cost));
    for (const row of goods) bump(row.supplier_id, num(row.qty) * num(row.unit_cost));
    bump(headSupplierId, num(freight));
    const rows = [...perSupplier.values()]
      .map((r) => ({ ...r, vat: r.subtotal * VAT_RATE, gross: r.subtotal * (1 + VAT_RATE) }))
      .sort((a, b) => b.gross - a.gross);
    const subtotal = sum(rows.map((r) => r.subtotal));
    const vat = sum(rows.map((r) => r.vat));
    return { rows, subtotal, vat, gross: subtotal + vat };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, goods, freight, headSupplierId, suppliers]);

  const missingSupplier = validItems.some((r) => !r.supplier_id) || validGoods.some((r) => !r.supplier_id);
  const canSave =
    Boolean(headSupplierId) &&
    !missingSupplier &&
    vehicleNo.trim().length > 0 &&
    validItems.length + validGoods.length > 0 &&
    !duplicateFuel &&
    !duplicateProduct &&
    !overAllocated;

  const save = (): void => {
    if (!canSave) return;
    const payload: FuelShipmentCreate = {
      supplier_id: headSupplierId,
      vehicle_no: vehicleNo.trim(),
      driver_name: driverName.trim() || null,
      shipment_date: shipmentDate || null,
      invoice_no: invoiceNo.trim() || null,
      freight_cost: freight || "0",
      note: note.trim() || null,
      items: validItems.map((row) => ({
        fuel_id: row.fuel_id,
        supplier_id: row.supplier_id || null,
        liters: row.liters,
        unit_cost: row.unit_cost,
        allocations: row.allocations
          .filter((a) => a.tank_id && num(a.liters) > 0)
          .map((a) => ({ tank_id: a.tank_id, liters: a.liters })),
      })),
      goods: validGoods.map((row) => ({
        product_id: row.product_id,
        supplier_id: row.supplier_id || null,
        qty: row.qty,
        unit_cost: row.unit_cost,
        allocations: row.allocations
          .filter((a) => a.branch_id && num(a.qty) > 0)
          .map((a) => ({ branch_id: a.branch_id, qty: a.qty })),
      })),
    };
    createMutation.mutate(payload, {
      onSuccess: (shipment) => {
        toastSuccess(t.shipments.created);
        navigate(`/shipments/${shipment.id}`, { replace: true });
      },
      onError: (error) => toastError(errorMessage(error)),
    });
  };

  // ------------------------------------------------------------ дэлгэц
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.shipments.newTitle}
        subtitle={t.shipments.newSubtitle}
        icon={<Truck className="h-6 w-6" />}
        iconTone="warning"
        actions={
          <Button variant="primary" size="lg" icon={<Save />} disabled={!canSave} loading={createMutation.isPending} onClick={save}>
            {t.common.save}
          </Button>
        }
      />

      <Card title={t.shipments.headerCard} subtitle={t.shipments.headerHint}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <TextField label={t.shipments.vehicleNo} value={vehicleNo} onChange={setVehicleNo} placeholder="1234 УБА" maxLength={32} />
          <TextField label={t.shipments.driver} value={driverName} onChange={setDriverName} maxLength={64} />
          <DateField label={t.common.date} value={shipmentDate} onChange={setShipmentDate} max={todayInput()} />
          <TextField label={t.shipments.invoiceNo} value={invoiceNo} onChange={setInvoiceNo} maxLength={64} />
          <NumberField name="freight" label={t.shipments.freight} value={freight} onChange={setFreight} suffix="₮" maxDecimals={2} hint={t.shipments.freightHint} />
          {num(freight) > 0 ? (
            <PickerField
              label={t.shipments.freightSupplier}
              value={freightSupplierId || firstLineSupplier}
              options={supplierOptions}
              onChange={setFreightSupplierId}
              searchable
            />
          ) : null}
        </div>
      </Card>

      {/* ---------------- Түлш ---------------- */}
      <Card
        title={t.shipments.fuelCard}
        subtitle={t.shipments.fuelCardHint}
        actions={
          <Button variant="secondary" size="md" icon={<Plus />} onClick={() => setItems((prev) => [...prev, newItem()])}>
            {t.shipments.addFuel}
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {items.length === 0 ? <p className="text-sm text-ink-soft">{t.shipments.noFuelRows}</p> : null}
          {items.map((row) => {
            const amount = num(row.liters) * num(row.unit_cost);
            const allocated = allocatedLiters(row);
            const left = num(row.liters) - allocated;
            const over = left < -0.0005;
            return (
              <div key={row.key} className="rounded-2xl border border-line bg-surface-alt/40 p-3 sm:p-4">
                <div className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[1.1fr_1.1fr_0.8fr_0.9fr_auto_auto]">
                  <PickerField label={t.shipments.fuel} value={row.fuel_id} options={fuelOptions} onChange={(value) => patchItem(row.key, { fuel_id: value, allocations: [] })} />
                  <PickerField label={t.procurement.supplier} value={row.supplier_id} options={lineSupplierOptions} onChange={(value) => patchItem(row.key, { supplier_id: value })} searchable />
                  <NumberField name={`liters-${row.key}`} label={t.common.liters} value={row.liters} onChange={(value) => patchItem(row.key, { liters: value })} suffix="л" maxDecimals={3} />
                  <NumberField name={`cost-${row.key}`} label={t.shipments.unitCost} value={row.unit_cost} onChange={(value) => patchItem(row.key, { unit_cost: value })} suffix="₮" maxDecimals={2} />
                  <div className="flex flex-col gap-1.5 pb-1">
                    <FieldLabel>{t.common.amount}</FieldLabel>
                    <span className="num font-bold text-ink">{formatMNT(amount)}</span>
                  </div>
                  <Button variant="ghost" size="md" icon={<Trash2 />} onClick={() => setItems((prev) => prev.filter((r) => r.key !== row.key))} aria-label={t.common.delete} />
                </div>

                {/* Хуваарилалт: салбар бүрийн саванд өөр хэмжээгээр */}
                <div className="mt-3 rounded-xl border border-dashed border-line-strong bg-white p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink">
                      <Droplets className="h-4 w-4 text-action" />
                      {t.shipments.allocationFuel}
                    </span>
                    <span className={`num text-xs font-semibold ${over ? "text-danger-dark" : left > 0.0005 ? "text-warning-dark" : "text-success-dark"}`}>
                      {t.shipments.allocated}: {formatNumber(allocated, 3)} л · {over ? t.shipments.overAllocated : `${t.shipments.unallocated}: ${formatNumber(Math.max(left, 0), 3)} л`}
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {row.allocations.map((alloc) => (
                      <div key={alloc.key} className="grid items-end gap-2 sm:grid-cols-[1.4fr_0.8fr_auto]">
                        <PickerField label={t.shipments.branchTank} value={alloc.tank_id} options={tankOptionsFor(row.fuel_id)} onChange={(value) => patchFuelAlloc(row.key, alloc.key, { tank_id: value })} disabled={!row.fuel_id} />
                        <NumberField name={`alloc-l-${alloc.key}`} label={t.common.liters} value={alloc.liters} onChange={(value) => patchFuelAlloc(row.key, alloc.key, { liters: value })} suffix="л" maxDecimals={3} />
                        <Button variant="ghost" size="md" icon={<Trash2 />} aria-label={t.common.delete} onClick={() => patchItem(row.key, { allocations: row.allocations.filter((a) => a.key !== alloc.key) })} />
                      </div>
                    ))}
                    <Button variant="secondary" size="md" icon={<Plus />} disabled={!row.fuel_id} onClick={() => patchItem(row.key, { allocations: [...row.allocations, newFuelAlloc()] })} className="self-start">
                      {t.shipments.addTank}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
          {duplicateFuel ? <p className="text-sm font-semibold text-danger-dark">{t.shipments.duplicateFuel}</p> : null}
        </div>
      </Card>

      {/* ---------------- Бараа ---------------- */}
      <Card
        title={t.shipments.goodsCard}
        subtitle={t.shipments.goodsCardHint}
        actions={
          <Button variant="secondary" size="md" icon={<Plus />} onClick={() => setGoods((prev) => [...prev, newGoods()])}>
            {t.shipments.addGoods}
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {goods.length === 0 ? <p className="text-sm text-ink-soft">{t.shipments.noGoodsRows}</p> : null}
          {goods.map((row) => {
            const product = products.find((p) => p.id === row.product_id);
            const unit = product?.unit ?? "";
            const amount = num(row.qty) * num(row.unit_cost);
            const allocated = allocatedQty(row);
            const left = num(row.qty) - allocated;
            const over = left < -0.0005;
            return (
              <div key={row.key} className="rounded-2xl border border-line bg-surface-alt/40 p-3 sm:p-4">
                <div className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_1.1fr_0.7fr_0.9fr_auto_auto]">
                  <PickerField label={t.shipments.product} value={row.product_id} options={productOptions} onChange={(value) => patchGoods(row.key, { product_id: value })} searchable />
                  <PickerField label={t.procurement.supplier} value={row.supplier_id} options={lineSupplierOptions} onChange={(value) => patchGoods(row.key, { supplier_id: value })} searchable />
                  <NumberField name={`qty-${row.key}`} label={t.common.qty} value={row.qty} onChange={(value) => patchGoods(row.key, { qty: value })} suffix={unit} maxDecimals={3} />
                  <NumberField name={`gcost-${row.key}`} label={t.shipments.unitCost} value={row.unit_cost} onChange={(value) => patchGoods(row.key, { unit_cost: value })} suffix="₮" maxDecimals={2} />
                  <div className="flex flex-col gap-1.5 pb-1">
                    <FieldLabel>{t.common.amount}</FieldLabel>
                    <span className="num font-bold text-ink">{formatMNT(amount)}</span>
                  </div>
                  <Button variant="ghost" size="md" icon={<Trash2 />} onClick={() => setGoods((prev) => prev.filter((r) => r.key !== row.key))} aria-label={t.common.delete} />
                </div>

                <div className="mt-3 rounded-xl border border-dashed border-line-strong bg-white p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink">
                      <Building2 className="h-4 w-4 text-violet" />
                      {t.shipments.allocationGoods}
                    </span>
                    <span className={`num text-xs font-semibold ${over ? "text-danger-dark" : left > 0.0005 ? "text-warning-dark" : "text-success-dark"}`}>
                      {t.shipments.allocated}: {formatNumber(allocated, 3)} {unit} · {over ? t.shipments.overAllocated : `${t.shipments.unallocated}: ${formatNumber(Math.max(left, 0), 3)} ${unit}`}
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {row.allocations.map((alloc) => (
                      <div key={alloc.key} className="grid items-end gap-2 sm:grid-cols-[1.4fr_0.8fr_auto]">
                        <PickerField label={t.branches.title} value={alloc.branch_id} options={branchOptions} onChange={(value) => patchGoodsAlloc(row.key, alloc.key, { branch_id: value })} />
                        <NumberField name={`alloc-q-${alloc.key}`} label={t.common.qty} value={alloc.qty} onChange={(value) => patchGoodsAlloc(row.key, alloc.key, { qty: value })} suffix={unit} maxDecimals={3} />
                        <Button variant="ghost" size="md" icon={<Trash2 />} aria-label={t.common.delete} onClick={() => patchGoods(row.key, { allocations: row.allocations.filter((a) => a.key !== alloc.key) })} />
                      </div>
                    ))}
                    <Button variant="secondary" size="md" icon={<Plus />} disabled={!row.product_id} onClick={() => patchGoods(row.key, { allocations: [...row.allocations, newGoodsAlloc()] })} className="self-start">
                      {t.shipments.addBranch}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
          {duplicateProduct ? <p className="text-sm font-semibold text-danger-dark">{t.shipments.duplicateProduct}</p> : null}
        </div>
      </Card>

      {/* ---------------- Нийлүүлэгч тус бүрийн дүн ---------------- */}
      <Card title={t.shipments.totalsCard} subtitle={t.shipments.totalsHint}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr className="text-left text-xs font-bold tracking-wider text-ink-soft uppercase">
                <th className="py-2 pr-3">{t.procurement.supplier}</th>
                <th className="py-2 pr-3 text-right">{t.shipments.subtotalNoVat}</th>
                <th className="py-2 pr-3 text-right">{t.common.vat}</th>
                <th className="py-2 text-right">{t.shipments.totalGross}</th>
              </tr>
            </thead>
            <tbody>
              {totals.rows.map((r) => (
                <tr key={r.name} className="border-t border-line">
                  <td className="py-2 pr-3 font-semibold text-ink">{r.name}</td>
                  <td className="num py-2 pr-3 text-right">{formatMNT(r.subtotal)}</td>
                  <td className="num py-2 pr-3 text-right">{formatMNT(r.vat)}</td>
                  <td className="num py-2 text-right font-bold">{formatMNT(r.gross)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-line-strong">
                <td className="py-2 pr-3 font-bold text-ink">{t.common.total}</td>
                <td className="num py-2 pr-3 text-right font-bold">{formatMNT(totals.subtotal)}</td>
                <td className="num py-2 pr-3 text-right font-bold">{formatMNT(totals.vat)}</td>
                <td className="num py-2 text-right text-lg font-bold text-success-dark">{formatMNT(totals.gross)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {overAllocated ? <p className="mt-3 text-sm font-semibold text-danger-dark">{t.shipments.overAllocatedHint}</p> : null}
        <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-ink-soft">
          <Package className="h-3.5 w-3.5" />
          {t.shipments.planHint}
        </p>
        <TextAreaField label={t.common.note} value={note} onChange={setNote} className="mt-4" />
      </Card>
    </div>
  );
}

export default FuelShipmentFormPage;
