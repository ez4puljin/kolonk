/**
 * Орлого авах — шатахуун ба барааг НЭГ баримтаар бүртгэнэ.
 *
 * Өмнө нь «Шатахуун таталт» ба «Худалдан авалт» хоёр тусдаа цэс, тусдаа
 * маягттай байсан. Нийлүүлэгч нэг өдөр хоёуланг нь авчирдаг тул хоёр
 * газар давхар бүртгэх шаардлагатай байв.
 *
 * Сервер тал дээр хоёулаа нэг гүйлгээнд бичигдэнэ: аль нэг мөр буруу бол
 * бүгд буцаж, хагас бүртгэгдсэн орлого үлдэхгүй.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Droplets, Package, Plus, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import { useReceiveMutation, useSuppliers } from "../../api/queries/procurement";
import { useProducts } from "../../api/queries/products";
import { useTanks } from "../../api/queries/tanks";
import type { UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { t } from "../../i18n/mn";
import { dToQty } from "../../lib/decimal";
import { formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, NumberField, PickerField, TextAreaField, TextField } from "../catalog/_shared";

interface FuelLine {
  key: string;
  tankId: string;
  liters: string;
  unitCost: string;
  freight: string;
}

interface GoodsLine {
  key: string;
  productId: string;
  qty: string;
  unitCost: string;
}

function todayInput(): string {
  const now = new Date();
  const pad = (value: number): string => String(value).padStart(2, "0");
  return [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join("-");
}

let counter = 0;
const nextKey = (): string => `row-${(counter += 1)}`;

export function ReceiveNewPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const tanksQuery = useTanks({ active_only: true });
  const productsQuery = useProducts({ active_only: true, limit: 500 });
  const branchesQuery = useBranches();
  const mutation = useReceiveMutation();

  const [supplierId, setSupplierId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [receiptDate, setReceiptDate] = useState(todayInput());
  const [invoiceNo, setInvoiceNo] = useState("");
  const [note, setNote] = useState("");
  const [fuels, setFuels] = useState<FuelLine[]>([]);
  const [goods, setGoods] = useState<GoodsLine[]>([]);
  const [error, setError] = useState<string | null>(null);

  const suppliers = suppliersQuery.data?.items ?? [];
  const tanks = tanksQuery.data?.items ?? [];
  const products = productsQuery.data?.items ?? [];
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );

  const fuelTotal = fuels.reduce(
    (sum, line) => sum + dToQty(line.liters || "0") * dToQty(line.unitCost || "0") + dToQty(line.freight || "0"),
    0,
  );
  const goodsTotal = goods.reduce(
    (sum, line) => sum + dToQty(line.qty || "0") * dToQty(line.unitCost || "0"),
    0,
  );
  const net = fuelTotal + goodsTotal;
  const vat = net * 0.1;

  const canSubmit =
    supplierId !== "" &&
    (fuels.some((line) => line.tankId && dToQty(line.liters || "0") > 0) ||
      goods.some((line) => line.productId && dToQty(line.qty || "0") > 0));

  const submit = (): void => {
    setError(null);
    mutation.mutate(
      {
        supplier_id: supplierId as UUID,
        receipt_date: receiptDate || null,
        invoice_no: invoiceNo || null,
        note: note || null,
        branch_id: (branchId || null) as UUID | null,
        fuels: fuels
          .filter((line) => line.tankId && dToQty(line.liters || "0") > 0)
          .map((line) => ({
            tank_id: line.tankId as UUID,
            liters: line.liters,
            unit_cost: line.unitCost || "0",
            freight_cost: line.freight || "0",
          })),
        items: goods
          .filter((line) => line.productId && dToQty(line.qty || "0") > 0)
          .map((line) => ({
            product_id: line.productId as UUID,
            qty: line.qty,
            unit_cost: line.unitCost || "0",
          })),
      },
      {
        onSuccess: (data) => {
          toastSuccess(t.procurement.received + ": " + formatMNT(data.total_gross));
          navigate("/purchases");
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.procurement.receiveTitle}
        subtitle={t.procurement.receiveHint}
        actions={
          <>
            <Button variant="secondary" size="lg" onClick={() => navigate("/purchases")}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="lg"
              disabled={!canSubmit}
              loading={mutation.isPending}
              onClick={submit}
            >
              {t.procurement.receiveAction}
            </Button>
          </>
        }
      />

      <Card title={t.procurement.docInfo}>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <PickerField
            label={t.procurement.supplier}
            value={supplierId}
            onChange={setSupplierId}
            options={suppliers.map((supplier) => ({ value: supplier.id, label: supplier.name }))}
          />
          <DateField label={t.common.date} value={receiptDate} onChange={setReceiptDate} />
          <TextField label={t.procurement.invoiceNo} value={invoiceNo} onChange={setInvoiceNo} />
          {branches.length > 1 ? (
            <PickerField
              label={t.branches.title}
              value={branchId}
              onChange={setBranchId}
              options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
            />
          ) : null}
        </div>
      </Card>

      {/* --- Шатахуун --- */}
      <Card
        title={t.procurement.fuelSection}
        subtitle={t.procurement.fuelSectionHint}
        actions={
          <Button
            variant="secondary"
            size="md"
            icon={<Plus />}
            onClick={() =>
              setFuels((prev) => [
                ...prev,
                { key: nextKey(), tankId: "", liters: "", unitCost: "", freight: "" },
              ])
            }
          >
            {t.common.add}
          </Button>
        }
      >
        {fuels.length === 0 ? (
          <p className="py-3 text-sm text-ink-soft">{t.procurement.noFuelLines}</p>
        ) : (
          <div className="flex flex-col gap-3">
            {fuels.map((line) => (
              <div
                key={line.key}
                className="flex flex-col gap-3 rounded-xl border border-line bg-surface-alt px-3 py-3 lg:flex-row lg:items-end"
              >
                <div className="min-w-0 flex-1">
                  <PickerField
                    label={t.tanks.tank}
                    value={line.tankId}
                    onChange={(value) =>
                      setFuels((prev) =>
                        prev.map((row) => (row.key === line.key ? { ...row, tankId: value } : row)),
                      )
                    }
                    options={tanks.map((tank) => ({
                      value: tank.id,
                      label: `${tank.name} · ${tank.fuel.name_mn}`,
                    }))}
                  />
                </div>
                <NumberField
                  name={`fuel-l-${line.key}`}
                  label={t.pos.liters}
                  value={line.liters}
                  onChange={(value) =>
                    setFuels((prev) =>
                      prev.map((row) => (row.key === line.key ? { ...row, liters: value } : row)),
                    )
                  }
                  maxDecimals={3}
                  className="lg:w-36"
                />
                <NumberField
                  name={`fuel-c-${line.key}`}
                  label={t.common.unitCost}
                  value={line.unitCost}
                  onChange={(value) =>
                    setFuels((prev) =>
                      prev.map((row) => (row.key === line.key ? { ...row, unitCost: value } : row)),
                    )
                  }
                  maxDecimals={2}
                  className="lg:w-36"
                />
                <NumberField
                  name={`fuel-f-${line.key}`}
                  label={t.procurement.freight}
                  value={line.freight}
                  onChange={(value) =>
                    setFuels((prev) =>
                      prev.map((row) => (row.key === line.key ? { ...row, freight: value } : row)),
                    )
                  }
                  maxDecimals={2}
                  className="lg:w-32"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 />}
                  title={t.common.delete}
                  aria-label={t.common.delete}
                  onClick={() => setFuels((prev) => prev.filter((row) => row.key !== line.key))}
                />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* --- Бараа материал --- */}
      <Card
        title={t.procurement.goodsSection}
        subtitle={t.procurement.goodsSectionHint}
        actions={
          <Button
            variant="secondary"
            size="md"
            icon={<Plus />}
            onClick={() =>
              setGoods((prev) => [
                ...prev,
                { key: nextKey(), productId: "", qty: "", unitCost: "" },
              ])
            }
          >
            {t.common.add}
          </Button>
        }
      >
        {goods.length === 0 ? (
          <p className="py-3 text-sm text-ink-soft">{t.procurement.noGoodsLines}</p>
        ) : (
          <div className="flex flex-col gap-3">
            {goods.map((line) => (
              <div
                key={line.key}
                className="flex flex-col gap-3 rounded-xl border border-line bg-surface-alt px-3 py-3 lg:flex-row lg:items-end"
              >
                <div className="min-w-0 flex-1">
                  <PickerField
                    label={t.products.product}
                    value={line.productId}
                    onChange={(value) =>
                      setGoods((prev) =>
                        prev.map((row) =>
                          row.key === line.key ? { ...row, productId: value } : row,
                        ),
                      )
                    }
                    options={products.map((product) => ({
                      value: product.id,
                      label: `${product.name_mn} · ${product.sku}`,
                    }))}
                  />
                </div>
                <NumberField
                  name={`goods-q-${line.key}`}
                  label={t.common.qty}
                  value={line.qty}
                  onChange={(value) =>
                    setGoods((prev) =>
                      prev.map((row) => (row.key === line.key ? { ...row, qty: value } : row)),
                    )
                  }
                  maxDecimals={3}
                  className="lg:w-36"
                />
                <NumberField
                  name={`goods-c-${line.key}`}
                  label={t.common.unitCost}
                  value={line.unitCost}
                  onChange={(value) =>
                    setGoods((prev) =>
                      prev.map((row) => (row.key === line.key ? { ...row, unitCost: value } : row)),
                    )
                  }
                  maxDecimals={2}
                  className="lg:w-36"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 />}
                  title={t.common.delete}
                  aria-label={t.common.delete}
                  onClick={() => setGoods((prev) => prev.filter((row) => row.key !== line.key))}
                />
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title={t.common.total}>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <span className="inline-flex items-center gap-2 text-ink-soft">
              <Droplets className="h-4 w-4" />
              {t.procurement.fuelSection}
            </span>
            <span className="num font-semibold text-ink">{formatMNT(String(fuelTotal))}</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="inline-flex items-center gap-2 text-ink-soft">
              <Package className="h-4 w-4" />
              {t.procurement.goodsSection}
            </span>
            <span className="num font-semibold text-ink">{formatMNT(String(goodsTotal))}</span>
          </div>
          <div className="flex items-baseline justify-between border-t border-line pt-2">
            <span className="text-ink-soft">{t.common.vat}</span>
            <span className="num font-semibold text-ink">{formatMNT(String(vat))}</span>
          </div>
          <div className="flex items-baseline justify-between border-t border-line pt-2">
            <span className="font-bold text-ink">{t.common.gross}</span>
            <span className="num text-xl font-bold text-ink">{formatMNT(String(net + vat))}</span>
          </div>
        </div>
      </Card>

      <TextAreaField label={t.common.note} value={note} onChange={setNote} />

      {error ? (
        <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default ReceiveNewPage;
