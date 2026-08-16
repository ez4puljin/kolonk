import { useEffect, useMemo, useState } from "react";
import { Save, Settings as SettingsIcon } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useSettings, useUpdateSettingMutation } from "../../api/queries/system";
import type { JsonValue } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { t } from "../../i18n/mn";
import { useUiStore } from "../../stores/ui";
import { NumberField, TextAreaField, TextField, ToggleField } from "../catalog/_shared";

type FieldKind = "text" | "textarea" | "number" | "rate" | "bool";

interface SettingField {
  key: string;
  label: string;
  kind: FieldKind;
  suffix?: string;
  hint?: string;
}

interface SettingGroup {
  key: string;
  title: string;
  fields: readonly SettingField[];
}

const GROUPS: readonly SettingGroup[] = [
  {
    key: "station",
    title: t.admin.stationName,
    fields: [
      { key: "station_name", label: t.admin.stationName, kind: "text" },
      { key: "station_address", label: t.admin.stationAddress, kind: "text" },
      { key: "station_phone", label: t.admin.stationPhone, kind: "text" },
      { key: "vat_payer_no", label: t.admin.vatPayerNo, kind: "text" },
    ],
  },
  {
    key: "vat",
    title: t.common.vat,
    fields: [
      {
        key: "vat_rate",
        label: t.admin.vatRate,
        kind: "rate",
        hint: "0.10 = 10%",
      },
    ],
  },
  {
    key: "receipt",
    title: t.sales.receipt,
    fields: [
      { key: "receipt_footer", label: t.admin.receiptFooter, kind: "textarea" },
      { key: "currency_symbol", label: t.admin.currencySymbol, kind: "text" },
    ],
  },
  {
    key: "ebarimt",
    title: t.sales.ebarimt,
    fields: [
      { key: "ebarimt_enabled", label: t.admin.ebarimtEnabled, kind: "bool" },
      { key: "ebarimt_pos_id", label: t.admin.ebarimtPosId, kind: "text" },
    ],
  },
  {
    key: "shift",
    title: t.shift.title,
    fields: [
      {
        key: "pos_sales_enabled",
        label: t.admin.posSalesEnabled,
        hint: t.admin.posSalesHint,
        kind: "bool",
      },
      {
        key: "shift_totalizer_enabled",
        label: t.admin.totalizerEnabled,
        kind: "bool",
        hint: t.admin.totalizerHint,
      },
    ],
  },
  {
    key: "printing",
    title: t.common.print,
    fields: [
      { key: "printer_width_mm", label: t.admin.printerWidth, kind: "number", suffix: t.units.mm },
      { key: "auto_print_receipt", label: t.admin.autoPrint, kind: "bool" },
    ],
  },
];

type DraftValue = string | boolean;

function toDraft(value: JsonValue | undefined, kind: FieldKind): DraftValue {
  if (kind === "bool") return value === true || value === "true";
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function toPayload(value: DraftValue, kind: FieldKind): JsonValue {
  if (kind === "bool") return value === true;
  if (kind === "number") {
    const parsed = Number(value === "" ? "0" : value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return String(value);
}

export function SettingsPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const settingsQuery = useSettings();
  const updateMutation = useUpdateSettingMutation();

  const [draft, setDraft] = useState<Record<string, DraftValue>>({});
  const [savingGroup, setSavingGroup] = useState<string | null>(null);

  const server = useMemo(() => settingsQuery.data ?? {}, [settingsQuery.data]);

  useEffect(() => {
    if (!settingsQuery.data) return;
    const next: Record<string, DraftValue> = {};
    for (const group of GROUPS) {
      for (const field of group.fields) {
        next[field.key] = toDraft(settingsQuery.data[field.key], field.kind);
      }
    }
    setDraft(next);
  }, [settingsQuery.data]);

  const isDirty = (group: SettingGroup): boolean =>
    group.fields.some((field) => {
      const current = draft[field.key];
      if (current === undefined) return false;
      return current !== toDraft(server[field.key], field.kind);
    });

  const saveGroup = async (group: SettingGroup): Promise<void> => {
    setSavingGroup(group.key);
    try {
      for (const field of group.fields) {
        const current = draft[field.key];
        if (current === undefined) continue;
        if (current === toDraft(server[field.key], field.kind)) continue;
        await updateMutation.mutateAsync({ key: field.key, value: toPayload(current, field.kind) });
      }
      toastSuccess(t.common.saved);
    } catch (error) {
      toastError(errorMessage(error));
    } finally {
      setSavingGroup(null);
    }
  };

  if (settingsQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (settingsQuery.isError) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.admin.settings} />
        <EmptyState
          icon={<SettingsIcon className="h-7 w-7" />}
          title={t.errors.loadFailed}
          hint={t.errors.server}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.admin.settings} subtitle={t.app.fullName} />

      <div className="grid gap-6 xl:grid-cols-2">
        {GROUPS.map((group) => (
          <Card
            key={group.key}
            title={group.title}
            actions={
              <Button
                variant="primary"
                size="md"
                icon={<Save />}
                disabled={!isDirty(group)}
                loading={savingGroup === group.key}
                onClick={() => void saveGroup(group)}
              >
                {t.common.save}
              </Button>
            }
          >
            <div className="flex flex-col gap-4">
              {group.fields.map((field) => {
                const value = draft[field.key] ?? (field.kind === "bool" ? false : "");

                if (field.kind === "bool") {
                  return (
                    <ToggleField
                      key={field.key}
                      label={field.label}
                      hint={field.hint}
                      value={value === true}
                      onChange={(next) => setDraft((current) => ({ ...current, [field.key]: next }))}
                    />
                  );
                }

                if (field.kind === "textarea") {
                  return (
                    <TextAreaField
                      key={field.key}
                      label={field.label}
                      value={typeof value === "string" ? value : ""}
                      onChange={(next) => setDraft((current) => ({ ...current, [field.key]: next }))}
                    />
                  );
                }

                if (field.kind === "number" || field.kind === "rate") {
                  return (
                    <NumberField
                      key={field.key}
                      name={`setting-${field.key}`}
                      label={field.label}
                      suffix={field.suffix}
                      hint={field.hint}
                      maxDecimals={field.kind === "rate" ? 4 : 0}
                      allowDecimal={field.kind === "rate"}
                      value={typeof value === "string" ? value : ""}
                      onChange={(next) => setDraft((current) => ({ ...current, [field.key]: next }))}
                    />
                  );
                }

                return (
                  <TextField
                    key={field.key}
                    label={field.label}
                    hint={field.hint}
                    value={typeof value === "string" ? value : ""}
                    onChange={(next) => setDraft((current) => ({ ...current, [field.key]: next }))}
                  />
                );
              })}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default SettingsPage;
