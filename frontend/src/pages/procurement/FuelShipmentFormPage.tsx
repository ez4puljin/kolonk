import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Save, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useFuels } from "../../api/queries/fuels";
import { useSuppliers } from "../../api/queries/procurement";
import { useCreateShipmentMutation } from "../../api/queries/shipments";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { t } from "../../i18n/mn";
import { formatMNT, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, FieldLabel, NumberField, PickerField, TextAreaField, TextField } from "../catalog/_shared";

const VAT_RATE = 0.1;

interface ItemDraft {
  key: number;
  fuel_id: string;
  liters: string;
  unit_cost: string;
}

let itemKey = 0;
const newItem = (): ItemDraft => ({ key: ++itemKey, fuel_id: "", liters: "", unit_cost: "" });

export function FuelShipmentFormPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [supplierId, setSupplierId] = useState("");
  const [vehicleNo, setVehicleNo] = useState("");
  const [driverName, setDriverName] = useState("");
  const [shipmentDate, setShipmentDate] = useState(todayInput());
  const [invoiceNo, setInvoiceNo] = useState("");
  const [freight, setFreight] = useState("");
  const [note, setNote] = useState("");
  const [items, setItems] = useState<ItemDraft[]>([newItem()]);

  const suppliersQuery = useSuppliers({ limit: 200, active_only: true });
  const fuelsQuery = useFuels();
  const createMutation = useCreateShipmentMutation();

  const supplierOptions = useMemo(
    () =>
      (suppliersQuery.data?.items ?? []).map((supplier) => ({
        value: supplier.id,
        label: supplier.name,
        hint: supplier.register_no ?? undefined,
      })),
    [suppliersQuery.data],
  );

  const fuels = useMemo(() => fuelsQuery.data?.items ?? [], [fuelsQuery.data]);
  const fuelOptions = useMemo(
    () => fuels.filter((fuel) => fuel.is_active).map((fuel) => ({ value: fuel.id, label: fuel.name_mn })),
    [fuels],
  );

  const patchItem = (key: number, patch: Partial<ItemDraft>): void => {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  };

  const totals = useMemo(() => {
    let subtotal = 0;
    for (const item of items) {
      const liters = Number(item.liters) || 0;
      const cost = Number(item.unit_cost) || 0;
      subtotal += liters * cost;
    }
    subtotal += Number(freight) || 0;
    const vat = subtotal * VAT_RATE;
    return { subtotal, vat, gross: subtotal + vat };
  }, [items, freight]);

  const validItems = items.filter(
    (item) => item.fuel_id && Number(item.liters) > 0 && Number(item.unit_cost) > 0,
  );
  const duplicateFuel = new Set(validItems.map((item) => item.fuel_id)).size !== validItems.length;
  const canSave =
    Boolean(supplierId) && vehicleNo.trim().length > 0 && validItems.length > 0 && !duplicateFuel;

  const save = (): void => {
    if (!canSave) return;
    createMutation.mutate(
      {
        supplier_id: supplierId,
        vehicle_no: vehicleNo.trim(),
        driver_name: driverName.trim() || null,
        shipment_date: shipmentDate || null,
        invoice_no: invoiceNo.trim() || null,
        freight_cost: freight || "0",
        note: note.trim() || null,
        items: validItems.map((item) => ({
          fuel_id: item.fuel_id,
          liters: item.liters,
          unit_cost: item.unit_cost,
        })),
      },
      {
        onSuccess: (shipment) => {
          toastSuccess("Ачилт үүслээ — бүртгэсний дараа түгээлт эхэлнэ");
          navigate(`/shipments/${shipment.id}`, { replace: true });
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Шинэ ачилт"
        subtitle="Нийлүүлэгчээс машинаар татсан түлшний бүртгэл"
        actions={
          <Button
            variant="primary"
            size="lg"
            icon={<Save />}
            disabled={!canSave}
            loading={createMutation.isPending}
            onClick={save}
          >
            {t.common.save}
          </Button>
        }
      />

      <Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PickerField
            label={t.procurement.supplier}
            value={supplierId}
            options={supplierOptions}
            onChange={setSupplierId}
          />
          <TextField label="Машины дугаар" value={vehicleNo} onChange={setVehicleNo} placeholder="1234 УБА" maxLength={32} />
          <TextField label="Жолооч" value={driverName} onChange={setDriverName} maxLength={64} />
          <DateField label="Огноо" value={shipmentDate} onChange={setShipmentDate} max={todayInput()} />
          <TextField label="Нэхэмжлэхийн дугаар" value={invoiceNo} onChange={setInvoiceNo} maxLength={64} />
          <NumberField
            name="freight"
            label="Тээврийн зардал (НӨАТ-гүй)"
            value={freight}
            onChange={setFreight}
            suffix="₮"
            maxDecimals={2}
            hint="Нэгж өртөгт литрээр хуваарилагдана"
          />
        </div>
      </Card>

      <Card
        title="Ачсан түлш"
        actions={
          <Button variant="secondary" size="md" icon={<Plus />} onClick={() => setItems((prev) => [...prev, newItem()])}>
            Түлш нэмэх
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          {items.map((item) => {
            const amount = (Number(item.liters) || 0) * (Number(item.unit_cost) || 0);
            return (
              <div
                key={item.key}
                className="grid items-end gap-3 rounded-xl border border-line bg-surface-alt/40 p-3 sm:grid-cols-[minmax(10rem,1.2fr)_1fr_1fr_auto_auto]"
              >
                <PickerField
                  label="Түлш"
                  value={item.fuel_id}
                  options={fuelOptions}
                  onChange={(value) => patchItem(item.key, { fuel_id: value })}
                />
                <NumberField
                  name={`liters-${item.key}`}
                  label="Литр"
                  value={item.liters}
                  onChange={(value) => patchItem(item.key, { liters: value })}
                  suffix="л"
                  maxDecimals={3}
                />
                <NumberField
                  name={`cost-${item.key}`}
                  label="Нэгж үнэ (НӨАТ-гүй)"
                  value={item.unit_cost}
                  onChange={(value) => patchItem(item.key, { unit_cost: value })}
                  suffix="₮"
                  maxDecimals={2}
                />
                <div className="flex flex-col gap-1.5 pb-1">
                  <FieldLabel>Дүн</FieldLabel>
                  <span className="num font-bold text-ink">{formatMNT(amount)}</span>
                </div>
                <Button
                  variant="ghost"
                  size="md"
                  icon={<Trash2 />}
                  disabled={items.length === 1}
                  onClick={() => setItems((prev) => prev.filter((row) => row.key !== item.key))}
                  aria-label={t.common.delete}
                />
              </div>
            );
          })}
          {duplicateFuel ? (
            <p className="text-sm font-semibold text-danger-dark">
              Нэг түлш давхардаж байна — мөрийг нэгтгэнэ үү.
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <FieldLabel>НӨАТ-гүй дүн (тээвэртэй)</FieldLabel>
            <span className="num text-lg font-bold text-ink">{formatMNT(totals.subtotal)}</span>
          </div>
          <div className="flex flex-col gap-1">
            <FieldLabel>НӨАТ 10%</FieldLabel>
            <span className="num text-lg font-bold text-ink">{formatMNT(totals.vat)}</span>
          </div>
          <div className="flex flex-col gap-1">
            <FieldLabel>Нийт төлөх дүн</FieldLabel>
            <span className="num text-xl font-bold text-success-dark">{formatMNT(totals.gross)}</span>
          </div>
        </div>
        <TextAreaField label={t.common.note} value={note} onChange={setNote} className="mt-4" />
      </Card>
    </div>
  );
}

export default FuelShipmentFormPage;
