/**
 * Өдрийн хаалтын цонх ба админы засварын цонхнуудын нийтлэг хэсгүүд.
 */
import { useMemo } from "react";

import { useCustomers } from "../../api/queries/partners";
import type { ClosingMethod, ClosingTarget } from "../../api/types";
import { t } from "../../i18n/mn";
import { PickerField, TextField } from "../../pages/catalog/_shared";
import { Button } from "../ui/Button";

export const T = t.closingWindow;

export const METHOD_LABEL: Record<ClosingMethod, string> = {
  cash: T.methodCash,
  card: T.methodCard,
  transfer: T.methodTransfer,
};

export const METHOD_OPTIONS = (["cash", "card", "transfer"] as const).map((value) => ({
  value,
  label: METHOD_LABEL[value],
}));

/** Харилцагчийн сонголтод «шинэ харилцагч»-ийн утга. */
export const NEW = "__new__";

/** Харилцагчийн сонголт — гэрээ / гэрээгүй харилцагч / шинэ. */
export function useTargetOptions(enabled: boolean) {
  const { data } = useCustomers({ q: "", active_only: true, limit: 500 });
  return useMemo(() => {
    if (!enabled) return [];
    const out: { value: string; label: string; hint?: string }[] = [{ value: NEW, label: T.newCustomer }];
    for (const customer of data?.items ?? []) {
      const active = customer.contracts.filter((c) => c.status === "active");
      const hint = customer.phone ?? undefined;
      if (active.length === 0) out.push({ value: `u:${customer.id}`, label: customer.full_name || customer.name, hint });
      for (const contract of active) {
        out.push({ value: `c:${contract.id}`, label: `${customer.full_name || customer.name} · ${contract.contract_no}`, hint });
      }
    }
    return out;
  }, [data, enabled]);
}

export function toTarget(value: string, name: string, phone: string): ClosingTarget | null {
  if (value === NEW) return name.trim() ? { new_customer: { name: name.trim(), phone: phone.trim() || null } } : null;
  if (value.startsWith("c:")) return { contract_id: value.slice(2) };
  if (value.startsWith("u:")) return { customer_id: value.slice(2) };
  return null;
}

export function DialogFooter({
  busy,
  disabled,
  onClose,
  onSave,
}: {
  busy: boolean;
  disabled?: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <>
      <Button variant="secondary" size="md" onClick={onClose}>
        {t.common.cancel}
      </Button>
      <Button variant="primary" size="md" loading={busy} disabled={disabled} onClick={onSave}>
        {t.common.save}
      </Button>
    </>
  );
}

export function TargetFields({
  value,
  onChange,
  name,
  onName,
  phone,
  onPhone,
  enabled,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  name: string;
  onName: (v: string) => void;
  phone: string;
  onPhone: (v: string) => void;
  enabled: boolean;
  /** Сонгосон утга жагсаалтад алга бол харуулах (одоогийн харилцагч). */
  placeholder?: string;
}) {
  const options = useTargetOptions(enabled);
  return (
    <>
      <PickerField label={T.customer} value={value} options={options} onChange={onChange} placeholder={placeholder} />
      {value === NEW ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label={T.newName} value={name} onChange={onName} />
          <TextField kind="tel" label={T.newPhone} value={phone} onChange={onPhone} />
        </div>
      ) : null}
    </>
  );
}

/** Тоо хэмжээг оруулгад — илүүдэл тэгийг таслана («2.000» → «2»). */
export function trimQty(value: string | null | undefined): string {
  if (value == null || value === "") return "";
  const text = String(value);
  return text.includes(".") ? text.replace(/\.?0+$/, "") : text;
}
