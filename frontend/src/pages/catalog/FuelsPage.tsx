import { useMemo, useState } from "react";
import { Droplets, Pencil, Plus } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useCreateFuelMutation, useFuels, useUpdateFuelMutation } from "../../api/queries/fuels";
import type { Fuel } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { ACTIVE_STATUS_META, statusMeta } from "../../lib/constants";
import { formatMNT } from "../../lib/format";
import { useCan } from "../../hooks/usePermission";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, FieldLabel, NumberField, TextField } from "./_shared";

/** Түгээгүүр, савны дүрсэнд ялгагдах бэлэн өнгөнүүд. */
const COLOR_PRESETS = ["#10B981", "#2563EB", "#F59E0B", "#EF4444", "#8B5CF6", "#0EA5E9", "#64748B"];

interface FuelDraft {
  code: string;
  name_mn: string;
  price_per_liter: string;
  color_hex: string;
  sort_order: string;
  is_active: boolean;
}

const EMPTY: FuelDraft = {
  code: "",
  name_mn: "",
  price_per_liter: "",
  color_hex: COLOR_PRESETS[1],
  sort_order: "0",
  is_active: true,
};

function toDraft(fuel: Fuel): FuelDraft {
  return {
    code: fuel.code,
    name_mn: fuel.name_mn,
    price_per_liter: fuel.price_per_liter,
    color_hex: fuel.color_hex,
    sort_order: String(fuel.sort_order),
    is_active: fuel.is_active,
  };
}

export function FuelsPage() {
  const canManage = useCan("products.manage");
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const fuelsQuery = useFuels({ active_only: false, limit: 200 });
  const createMutation = useCreateFuelMutation();
  const updateMutation = useUpdateFuelMutation();

  const [editing, setEditing] = useState<Fuel | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<FuelDraft>(EMPTY);

  const fuels = useMemo(() => fuelsQuery.data?.items ?? [], [fuelsQuery.data]);
  const patch = (next: Partial<FuelDraft>): void => setDraft((prev) => ({ ...prev, ...next }));

  const openCreate = (): void => {
    setDraft({ ...EMPTY, sort_order: String(fuels.length + 1) });
    setCreating(true);
  };
  const openEdit = (fuel: Fuel): void => {
    setDraft(toDraft(fuel));
    setEditing(fuel);
  };
  const close = (): void => {
    setCreating(false);
    setEditing(null);
  };

  const canSave = draft.code.trim().length > 0 && draft.name_mn.trim().length > 0;
  const saving = createMutation.isPending || updateMutation.isPending;

  const save = (): void => {
    if (!canSave) return;
    if (editing) {
      // Үнийг энд өөрчлөхгүй — зөвхөн үнийн өөрчлөлтийн хүсэлтээр (батлагддаг).
      updateMutation.mutate(
        {
          id: editing.id,
          payload: {
            code: draft.code.trim(),
            name_mn: draft.name_mn.trim(),
            color_hex: draft.color_hex,
            sort_order: Number(draft.sort_order) || 0,
            is_active: draft.is_active,
          },
        },
        {
          onSuccess: () => {
            toastSuccess(t.common.saved);
            close();
          },
          onError: (error) => toastError(errorMessage(error)),
        },
      );
      return;
    }
    createMutation.mutate(
      {
        code: draft.code.trim(),
        name_mn: draft.name_mn.trim(),
        price_per_liter: draft.price_per_liter || "0",
        color_hex: draft.color_hex,
        sort_order: Number(draft.sort_order) || 0,
        is_active: draft.is_active,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          close();
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  const columns: Column<Fuel>[] = [
    {
      key: "name",
      header: "Түлш",
      primary: true,
      render: (row) => (
        <span className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 shrink-0 rounded-full" style={{ backgroundColor: row.color_hex }} />
          <span className="font-bold">{row.name_mn}</span>
          <span className="num text-ink-soft">{row.code}</span>
        </span>
      ),
    },
    {
      key: "price",
      header: "Литрийн үнэ",
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.price_per_liter)}</span>,
    },
    {
      key: "sort",
      header: "Дараалал",
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => row.sort_order,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => (
        <StatusBadge size="sm" meta={statusMeta(ACTIVE_STATUS_META, row.is_active ? "active" : "inactive")} />
      ),
    },
    ...(canManage
      ? [
          {
            key: "actions",
            header: t.common.actions,
            align: "right" as const,
            render: (row: Fuel) => (
              <Button variant="secondary" size="md" icon={<Pencil />} onClick={() => openEdit(row)}>
                {t.common.edit}
              </Button>
            ),
          },
        ]
      : []),
  ];

  const modalOpen = creating || editing !== null;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Түлш"
        subtitle="Станцад зарагдах түлшний төрлүүд — сав, түгээгүүр эдгээрээс сонгогдоно"
        actions={
          canManage ? (
            <Button variant="primary" size="lg" icon={<Plus />} onClick={openCreate}>
              Шинэ түлш
            </Button>
          ) : undefined
        }
      />

      <Card flush>
        <DataTable
          columns={columns}
          rows={fuels}
          rowKey={(row) => row.id}
          loading={fuelsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Droplets className="h-7 w-7" />}
              title="Түлш бүртгэгдээгүй байна"
              hint="Эхлээд түлшний төрлүүдээ (АИ-92, АИ-95, Дизель…) нэмнэ, дараа нь салбарын тохиргоонд сав, түгээгүүр үүсгэнэ"
              action={
                canManage ? (
                  <Button variant="primary" size="md" icon={<Plus />} onClick={openCreate}>
                    Шинэ түлш
                  </Button>
                ) : undefined
              }
            />
          }
        />
      </Card>

      <Modal
        open={modalOpen}
        onClose={close}
        size="md"
        title={editing ? "Түлш засах" : "Шинэ түлш"}
        subtitle={editing ? editing.name_mn : undefined}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={close}>
              {t.common.cancel}
            </Button>
            <Button variant="primary" size="md" disabled={!canSave} loading={saving} onClick={save}>
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label="Код"
            value={draft.code}
            onChange={(value) => patch({ code: value.toUpperCase() })}
            placeholder="AI92"
            maxLength={16}
            hint="Богино латин код — тайлан, баримтад харагдана"
          />
          <TextField
            label="Нэр"
            value={draft.name_mn}
            onChange={(value) => patch({ name_mn: value })}
            placeholder="АИ-92"
            maxLength={64}
          />
          {editing ? (
            <div className="flex flex-col gap-1.5">
              <FieldLabel>Литрийн үнэ</FieldLabel>
              <span className="num text-lg font-bold text-ink">{formatMNT(editing.price_per_liter)}</span>
              <span className="text-xs text-ink-soft">
                Үнийг «Үнийн өөрчлөлт» цэсээр хүсэлт гаргаж батлуулан солино.
              </span>
            </div>
          ) : (
            <NumberField
              name="fuel-price"
              label="Литрийн үнэ (анхны)"
              value={draft.price_per_liter}
              onChange={(value) => patch({ price_per_liter: value })}
              suffix="₮"
              maxDecimals={2}
              hint="Дараа нь зөвхөн үнийн өөрчлөлтийн хүсэлтээр солигдоно"
            />
          )}
          <div className="flex flex-col gap-1.5">
            <FieldLabel>Өнгө</FieldLabel>
            <div className="flex flex-wrap items-center gap-2">
              {COLOR_PRESETS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={color}
                  onClick={() => patch({ color_hex: color })}
                  className={[
                    "h-9 w-9 rounded-full border-2 transition-transform",
                    draft.color_hex.toUpperCase() === color ? "scale-110 border-ink" : "border-transparent",
                  ].join(" ")}
                  style={{ backgroundColor: color }}
                />
              ))}
              <input
                type="color"
                value={draft.color_hex}
                onChange={(event) => patch({ color_hex: event.target.value.toUpperCase() })}
                className="h-9 w-12 cursor-pointer rounded-lg border border-line bg-white"
                aria-label="Өөр өнгө"
              />
            </div>
          </div>
          <NumberField
            name="fuel-sort"
            label="Дараалал"
            value={draft.sort_order}
            onChange={(value) => patch({ sort_order: value })}
            allowDecimal={false}
            hint="Касс, тайланд харагдах дараалал (бага нь эхэнд)"
          />
          {editing ? (
            <ChipGroup<"active" | "inactive">
              label={t.common.status}
              value={draft.is_active ? "active" : "inactive"}
              onChange={(value) => patch({ is_active: value === "active" })}
              options={[
                { value: "active", label: t.common.active },
                { value: "inactive", label: t.common.inactive },
              ]}
            />
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default FuelsPage;
