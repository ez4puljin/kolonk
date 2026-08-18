import { useMemo, useState } from "react";
import { ArrowLeftRight, Boxes, ClipboardList, Scissors } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import {
  useBranchTransferMutation,
  useInventory,
} from "../../api/queries/inventory";
import { useProductCategories } from "../../api/queries/products";
import type { InventoryRow, ProductSaleMode } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { BulkConvertDialog } from "../../components/pos/BulkConvertDialog";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { useCan } from "../../hooks/usePermission";
import { OpeningBalanceModal } from "./OpeningBalanceModal";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { dMul, dSum, dToNumber, dToQty } from "../../lib/decimal";
import { formatMNT, formatQty } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  matchesQuery,
  NumberField,
  Pager,
  PickerField,
  SearchInput,
  TextAreaField,
} from "./_shared";

/** Мөрийн үнэлгээ — сервер талын нэр өөр байж болох тул өөрсдөө боддог. */
function rowValue(row: InventoryRow): string {
  return dMul(row.avg_cost, dToQty(row.stock_qty));
}

export function InventoryPage() {
  const canManage = useCan("inventory.manage");
  const canConvert = useCan("inventory.convert");
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [lowOnly, setLowOnly] = useState<"all" | "low">("all");
  const [modeFilter, setModeFilter] = useState<"all" | ProductSaleMode>("all");
  const [offset, setOffset] = useState(0);
  const [convertOpen, setConvertOpen] = useState(false);

  const [openingOpen, setOpeningOpen] = useState(false);

  // Салбар хоорондын шилжүүлэг
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferProductId, setTransferProductId] = useState("");
  const [transferFrom, setTransferFrom] = useState("");
  const [transferTo, setTransferTo] = useState("");
  const [transferQty, setTransferQty] = useState("");
  const [transferNote, setTransferNote] = useState("");
  const [transferError, setTransferError] = useState<string | null>(null);

  const categoriesQuery = useProductCategories();
  const branchesQuery = useBranches();
  const inventoryQuery = useInventory({
    category_id: categoryId || undefined,
    branch_id: branchId || undefined,
    low_stock: lowOnly === "low" ? true : undefined,
    sale_mode: modeFilter === "all" ? undefined : modeFilter,
    limit: 1000,
  });
  const transferMutation = useBranchTransferMutation();

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  /** Салбарын багана — «Бүх салбар» горимд, олон салбартай үед л харагдана. */
  const showBranchColumns = branchId === "" && branches.length > 1;

  const allRows = useMemo(() => inventoryQuery.data?.items ?? [], [inventoryQuery.data]);
  const filtered = useMemo(
    () => allRows.filter((row) => matchesQuery([row.name_mn, row.sku], query)),
    [allRows, query],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totals = useMemo(
    () => ({
      qty: dSum(filtered.map((row) => row.stock_qty)),
      value: dSum(filtered.map((row) => rowValue(row))),
      low: filtered.filter((row) => row.is_low).length,
    }),
    [filtered],
  );

  const categoryOptions = useMemo(
    () => [
      { value: "", label: t.pos.allCategories },
      ...(categoriesQuery.data?.items ?? []).map((category) => ({
        value: category.id,
        label: category.name_mn,
      })),
    ],
    [categoriesQuery.data],
  );


  const columns: Column<InventoryRow>[] = [
    { key: "name", header: t.products.product, primary: true, render: (row) => <span className="font-semibold">{row.name_mn}</span> },
    { key: "sku", header: t.products.sku, numeric: true, render: (row) => row.sku },
    {
      key: "category",
      header: t.products.category,
      hideOnMobile: true,
      render: (row) => row.category_name ?? "—",
    },
    ...(showBranchColumns
      ? branches.map(
          (branch): Column<InventoryRow> => ({
            key: `branch-${branch.id}`,
            header: branch.name,
            align: "right",
            numeric: true,
            hideOnMobile: true,
            render: (row) => {
              const entry = row.branches.find((item) => item.branch_id === branch.id);
              if (!entry || dToQty(entry.qty) === 0) return "—";
              // Тухайн САЛБАРЫН үлдэгдэл доод хязгаараас доош орсон эсэх —
              // нийт үлдэгдэл хангалттай ч нэг салбарт дуусах нь бий.
              const low = dToQty(entry.qty) <= dToQty(row.min_stock);
              return (
                <span className={low ? "font-bold text-danger-dark" : ""}>
                  {formatQty(entry.qty)}
                  {low ? <span className="ml-1 font-semibold">({t.pos.lowStock})</span> : null}
                </span>
              );
            },
          }),
        )
      : []),
    {
      key: "min_stock",
      header: t.products.minStock,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatQty(row.min_stock),
    },
    {
      key: "avg_cost",
      header: t.tanks.avgCost,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.avg_cost),
    },
    {
      key: "value",
      header: t.inventory.value,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(rowValue(row))}</span>,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.inventory.title}
        subtitle={t.inventory.valuation}
        actions={
          <>
            {canManage && branches.length > 1 ? (
              <Button
                variant="secondary"
                size="lg"
                icon={<ArrowLeftRight />}
                onClick={() => {
                  setTransferOpen(true);
                  setTransferError(null);
                }}
              >
                {t.inventory.transferTitle}
              </Button>
            ) : null}
            {canConvert ? (
              <Button variant="secondary" size="lg" icon={<Scissors />} onClick={() => setConvertOpen(true)}>
                {t.inventory.convertTitle}
              </Button>
            ) : null}
            {canManage ? (
              <Button
                variant="primary"
                size="lg"
                icon={<ClipboardList />}
                onClick={() => setOpeningOpen(true)}
              >
                {t.products.openingStock}
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.inventory.onHand} value={formatQty(totals.qty)} tone="neutral" />
        <StatBox label={t.inventory.value} value={formatMNT(totals.value)} tone="success" size="lg" />
        <StatBox label={t.pos.lowStock} value={totals.low} tone={totals.low > 0 ? "danger" : "neutral"} />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
        />
        <PickerField
          label={t.products.category}
          value={categoryId}
          options={categoryOptions}
          onChange={(next) => {
            setCategoryId(next);
            setOffset(0);
          }}
          className="min-w-[14rem]"
        />
        {branches.length > 1 ? (
          <PickerField
            label={t.branches.title}
            value={branchId}
            options={[
              { value: "", label: t.branches.allBranches },
              ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
            ]}
            onChange={(next) => {
              setBranchId(next);
              setOffset(0);
            }}
            className="min-w-[12rem]"
          />
        ) : null}
        <ChipGroup<"all" | ProductSaleMode>
          value={modeFilter}
          onChange={(next) => {
            setModeFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "piece", label: t.products.salePiece },
            { value: "bulk", label: t.products.saleBulk },
          ]}
        />
        <ChipGroup<"all" | "low">
          value={lowOnly}
          onChange={(next) => {
            setLowOnly(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "low", label: t.inventory.lowStockOnly },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.product_id}
          loading={inventoryQuery.isLoading}
          rowClassName={(row) => (row.is_low ? "bg-danger-soft/30" : "")}
          empty={<EmptyState icon={<Boxes className="h-7 w-7" />} title={t.common.empty} hint={t.common.emptyHint} />}
          footer={
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <span className="text-sm font-semibold text-ink-soft">
                  {t.common.total} · {filtered.length} {t.common.rows}
                </span>
                <span className="num text-2xl font-bold text-ink">{formatMNT(totals.value)}</span>
              </div>
              <Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />
            </div>
          }
        />
      </Card>

      <BulkConvertDialog
        open={convertOpen}
        onClose={() => setConvertOpen(false)}
        branchId={branchId || null}
      />

      {/* Салбар хоорондын шилжүүлэг — нийт нөөц хөдлөхгүй, өртөг хамт явна */}
      <Modal
        open={transferOpen}
        onClose={() => setTransferOpen(false)}
        size="md"
        title={t.inventory.transferTitle}
        subtitle={t.inventory.transferHint}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setTransferOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={
                transferProductId === "" ||
                transferFrom === "" ||
                transferTo === "" ||
                transferFrom === transferTo ||
                dToNumber(transferQty) <= 0
              }
              loading={transferMutation.isPending}
              onClick={() => {
                setTransferError(null);
                transferMutation.mutate(
                  {
                    product_id: transferProductId,
                    from_branch_id: transferFrom,
                    to_branch_id: transferTo,
                    qty: transferQty,
                    note: transferNote.trim() || null,
                  },
                  {
                    onSuccess: () => {
                      toastSuccess(t.inventory.transferDone);
                      setTransferOpen(false);
                      setTransferProductId("");
                      setTransferQty("");
                      setTransferNote("");
                    },
                    onError: (cause) => setTransferError(errorMessage(cause)),
                  },
                );
              }}
            >
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <PickerField
            label={t.products.product}
            value={transferProductId}
            options={allRows.map((row) => ({
              value: row.product_id,
              label: `${row.name_mn} · ${formatQty(row.stock_qty, row.unit)}`,
            }))}
            onChange={setTransferProductId}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <PickerField
              label={t.inventory.transferFrom}
              value={transferFrom}
              options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
              onChange={setTransferFrom}
            />
            <PickerField
              label={t.inventory.transferTo}
              value={transferTo}
              options={branches
                .filter((branch) => branch.id !== transferFrom)
                .map((branch) => ({ value: branch.id, label: branch.name }))}
              onChange={setTransferTo}
            />
          </div>
          <NumberField
            name="inventory-transfer-qty"
            label={t.inventory.adjustQty}
            value={transferQty}
            onChange={setTransferQty}
            maxDecimals={3}
            hint={
              transferProductId && transferFrom
                ? `${t.inventory.onHand}: ${formatQty(
                    allRows
                      .find((row) => row.product_id === transferProductId)
                      ?.branches.find((item) => item.branch_id === transferFrom)?.qty ?? "0",
                  )}`
                : undefined
            }
          />
          <TextAreaField label={t.common.note} value={transferNote} onChange={setTransferNote} />

          {transferError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {transferError}
            </p>
          ) : null}
        </div>
      </Modal>


      <OpeningBalanceModal
        open={openingOpen}
        onClose={() => setOpeningOpen(false)}
        branchId={branchId}
      />
    </div>
  );
}

export default InventoryPage;
