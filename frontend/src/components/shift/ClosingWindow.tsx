/**
 * Ээлжийн тайлан — өдрийн хаалтын цонх.
 *
 * Түгээгчийн өдрийн хаалтыг цонхных нь дарааллаар (тушаалт, тос, зээл,
 * өглөг төлөлт, зарлага, тулгалт) СЕРВЕРТ БҮРТГЭГДСЭН байдлаар нь харуулж,
 * түгээгчийн дэлгэц дээр харсан тулгалттай харьцуулна. Нягтлан/админ
 * (shifts.approve) батлагдаагүй хаалтыг энд засна.
 */
import { useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, Pencil, Plus, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useExpenseCategories } from "../../api/queries/expenses";
import { useCustomers } from "../../api/queries/partners";
import { useClosingEditMutation, useClosingFuels, useClosingView } from "../../api/queries/shifts";
import type { ClosingMethod, ClosingTarget, ClosingView, MoneyStr, UUID } from "../../api/types";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { dIsZero, dSub, dSum, dToQty } from "../../lib/decimal";
import { formatLiters, formatMoneyExact } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, PickerField, TextField } from "../../pages/catalog/_shared";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

const T = t.closingWindow;
const METHOD_LABEL: Record<ClosingMethod, string> = {
  cash: T.methodCash,
  card: T.methodCard,
  transfer: T.methodTransfer,
};
const METHOD_OPTIONS = (["cash", "card", "transfer"] as const).map((value) => ({ value, label: METHOD_LABEL[value] }));
const NEW = "__new__";

function Row({ label, value, strong, negative }: { label: ReactNode; value: MoneyStr; strong?: boolean; negative?: boolean }) {
  return (
    <div className="num flex items-baseline justify-between gap-3 py-1 text-[15px]">
      <span className={strong ? "font-bold text-ink" : "text-ink-soft"}>{label}</span>
      <span className={`${strong ? "text-lg font-black" : "font-semibold"} ${negative ? "text-danger-dark" : "text-ink"}`}>
        {negative ? "−" : ""}
        {formatMoneyExact(value)}
      </span>
    </div>
  );
}

function diffTone(value: MoneyStr): string {
  const n = Number(value);
  return n < 0 ? "border-danger bg-danger-soft text-danger-dark" : n > 0 ? "border-warning bg-warning-soft text-warning-dark" : "border-success bg-success-soft text-success-dark";
}

/** Харилцагчийн сонголт — гэрээ / гэрээгүй харилцагч / шинэ. */
function useTargetOptions(enabled: boolean) {
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

function toTarget(value: string, name: string, phone: string): ClosingTarget | null {
  if (value === NEW) return name.trim() ? { new_customer: { name: name.trim(), phone: phone.trim() || null } } : null;
  if (value.startsWith("c:")) return { contract_id: value.slice(2) };
  if (value.startsWith("u:")) return { customer_id: value.slice(2) };
  return null;
}

type Dialog = null | "tenders" | "credit" | "ar" | "expense";

export function ClosingWindow({ shiftId }: { shiftId: UUID }) {
  const { can } = usePermission();
  const canEdit = can("shifts.approve");
  const viewQuery = useClosingView(shiftId);
  const edit = useClosingEditMutation(shiftId);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [removing, setRemoving] = useState<null | { kind: "remove-credit" | "remove-ar" | "remove-expense"; id: UUID; label: string }>(null);

  const view = viewQuery.data;
  const editable = Boolean(view?.editable && canEdit);

  if (viewQuery.isLoading) {
    return (
      <Card title={T.title}>
        <div className="flex justify-center py-8">
          <Spinner label={t.common.loading} />
        </div>
      </Card>
    );
  }
  if (!view) return null;

  const run = (payload: Parameters<typeof edit.mutate>[0], done?: () => void): void =>
    edit.mutate(payload, {
      onSuccess: () => {
        toastSuccess(T.saved);
        done?.();
      },
      onError: (cause) => toastError(errorMessage(cause)),
    });

  const client = view.client;
  const clientDiff = client?.diff != null ? String(client.diff) : null;
  const gap = clientDiff !== null ? dSub(view.diff, clientDiff) : null;

  const removeButton = (kind: "remove-credit" | "remove-ar" | "remove-expense", id: UUID, label: string) =>
    editable ? (
      <Button variant="ghost" size="sm" icon={<Trash2 />} onClick={() => setRemoving({ kind, id, label })} aria-label={T.remove} />
    ) : null;

  const section = (title: string, total: MoneyStr, onAdd: (() => void) | null, children: ReactNode) => (
    <div className="flex flex-col gap-2 rounded-xl border border-line px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-bold text-ink">{title}</span>
        <span className="flex items-center gap-2">
          <span className="num font-bold text-ink">{formatMoneyExact(total)}</span>
          {onAdd && editable ? (
            <Button variant="secondary" size="sm" icon={<Plus />} onClick={onAdd}>
              {T.add}
            </Button>
          ) : null}
        </span>
      </div>
      {children}
    </div>
  );

  return (
    <Card title={T.title} subtitle={T.subtitle}>
      <div className="flex flex-col gap-4">
        {/* Тулгалт — сервер ба түгээгчийн дэлгэц */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1 rounded-xl border border-line-strong px-4 py-3">
            <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">{T.server}</span>
            <Row label={t.attendant.mustHandover} value={view.must} />
            <Row label={t.attendant.handedOver} value={view.handed} />
            <div className={`num mt-1 flex items-baseline justify-between rounded-lg border-2 px-3 py-2 ${diffTone(view.diff)}`}>
              <span className="text-sm font-bold">{t.attendant.diff}</span>
              <span className="text-xl font-black">{formatMoneyExact(view.diff)}</span>
            </div>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-line px-4 py-3">
            <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">{T.client}</span>
            {client && clientDiff !== null ? (
              <>
                <Row label={t.attendant.mustHandover} value={String(client.must ?? "0")} />
                <Row label={t.attendant.handedOver} value={String(client.handed ?? "0")} />
                <div className={`num mt-1 flex items-baseline justify-between rounded-lg border-2 px-3 py-2 ${diffTone(clientDiff)}`}>
                  <span className="text-sm font-bold">{t.attendant.diff}</span>
                  <span className="text-xl font-black">{formatMoneyExact(clientDiff)}</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-ink-soft">{T.clientMissing}</p>
            )}
          </div>
        </div>

        {gap !== null && !dIsZero(gap) ? (
          <p className="flex gap-2 rounded-xl border-2 border-danger bg-danger-soft px-3 py-2.5 text-sm text-danger-dark">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            {T.clientMismatch
              .replace("{client}", formatMoneyExact(clientDiff ?? "0"))
              .replace("{server}", formatMoneyExact(view.diff))
              .replace("{gap}", formatMoneyExact(gap))}
          </p>
        ) : null}
        {!view.consistent ? (
          <p className="rounded-xl border-2 border-warning bg-warning-soft px-3 py-2.5 text-sm text-warning-dark">{T.inconsistent}</p>
        ) : null}
        {canEdit && !view.editable ? <p className="text-sm text-ink-soft">{T.approvedLocked}</p> : null}
        {editable ? <p className="text-xs text-ink-soft">{T.editHint}</p> : null}

        {/* Тушаалт */}
        <div className="flex flex-col gap-1 rounded-xl border border-line px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-bold text-ink">{T.tenders}</span>
            {editable ? (
              <Button variant="secondary" size="sm" icon={<Pencil />} onClick={() => setDialog("tenders")}>
                {T.edit}
              </Button>
            ) : null}
          </div>
          <Row label={t.shift.declaredCash} value={view.declared_cash} />
          <Row label={T.methodCard} value={view.settlement_total} />
          <Row label={T.methodTransfer} value={view.transfer_total} />
          <Row label={t.attendant.handedOver} value={view.handed} strong />
        </div>

        {/* Тушаах ёстой задаргаа */}
        <div className="flex flex-col gap-0.5 rounded-xl border border-line bg-surface-alt px-3 py-2.5">
          <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">{T.mustHow}</span>
          <Row label={`+ ${t.shift.openingCash}`} value={view.opening_cash} />
          <Row label={`+ ${T.fuelByMile}`} value={view.fuel_total} />
          <Row label={`+ ${T.oil}`} value={view.oil_total} />
          {!dIsZero(view.credit_goods) ? <Row label={`+ ${T.credit} (${t.products.title})`} value={view.credit_goods} /> : null}
          <Row label={`+ ${T.ar}`} value={view.ar_total} />
          <Row label={T.credit} value={view.credit_total} negative />
          <Row label={T.expenseCash} value={view.expense_by_method.cash} negative />
          <Row label={t.attendant.mustHandover} value={view.must} strong />
        </div>

        {section(
          T.oil,
          view.oil_total,
          null,
          view.oil_lines.length === 0 ? (
            <span className="text-sm text-ink-faint">{T.none}</span>
          ) : (
            view.oil_lines.map((line, index) => (
              <div key={index} className="num flex justify-between gap-2 text-sm">
                <span className="text-ink">
                  {line.name} · {formatLiters(line.qty, 0)} × {formatMoneyExact(line.unit_price)}
                </span>
                <span className="font-semibold">{formatMoneyExact(line.amount)}</span>
              </div>
            ))
          ),
        )}

        {section(
          T.credit,
          view.credit_total,
          () => setDialog("credit"),
          view.credit_lines.length === 0 ? (
            <span className="text-sm text-ink-faint">{T.none}</span>
          ) : (
            view.credit_lines.map((line) => (
              <div key={line.sale_id} className="flex items-start justify-between gap-2 border-t border-line pt-1.5 first:border-t-0 first:pt-0">
                <div className="min-w-0 text-sm">
                  <div className="font-semibold text-ink">
                    {line.customer} {line.contract_no ? <span className="text-ink-soft">· {line.contract_no}</span> : null}
                    {line.edited ? <span className="ml-1 text-xs text-warning-dark">({T.edited})</span> : null}
                  </div>
                  <div className="num text-ink-soft">
                    {line.items.map((item) => `${item.name} ${formatLiters(item.qty, 2)}`).join(" · ")}
                  </div>
                </div>
                <span className="flex shrink-0 items-center gap-1">
                  <span className="num font-semibold">{formatMoneyExact(line.total)}</span>
                  {line.fuel_only ? removeButton("remove-credit", line.sale_id, `${line.customer} · ${formatMoneyExact(line.total)}`) : null}
                </span>
              </div>
            ))
          ),
        )}

        {section(
          T.ar,
          view.ar_total,
          () => setDialog("ar"),
          view.ar_payments.length === 0 ? (
            <span className="text-sm text-ink-faint">{T.none}</span>
          ) : (
            view.ar_payments.map((pay) => (
              <div key={pay.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 text-ink">
                  {pay.customer} · <span className="text-ink-soft">{METHOD_LABEL[pay.method]}</span>
                  {pay.edited ? <span className="ml-1 text-xs text-warning-dark">({T.edited})</span> : null}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <span className="num font-semibold">{formatMoneyExact(pay.amount)}</span>
                  {removeButton("remove-ar", pay.id, `${pay.customer} · ${formatMoneyExact(pay.amount)}`)}
                </span>
              </div>
            ))
          ),
        )}

        {section(
          T.expense,
          dSum(view.expenses.map((exp) => exp.amount)),
          () => setDialog("expense"),
          view.expenses.length === 0 ? (
            <span className="text-sm text-ink-faint">{T.none}</span>
          ) : (
            view.expenses.map((exp) => (
              <div key={exp.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 text-ink">
                  {exp.account_name} · <span className="text-ink-soft">{METHOD_LABEL[exp.method]}</span>
                  {exp.description ? <span className="text-ink-faint"> · {exp.description}</span> : null}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <span className="num font-semibold">{formatMoneyExact(exp.amount)}</span>
                  {removeButton("remove-expense", exp.id, `${exp.account_name} · ${formatMoneyExact(exp.amount)}`)}
                </span>
              </div>
            ))
          ),
        )}
      </div>

      {editable ? (
        <>
          <TendersDialog open={dialog === "tenders"} view={view} busy={edit.isPending} onClose={() => setDialog(null)} onSave={(body) => run({ kind: "tenders", ...body }, () => setDialog(null))} />
          <CreditDialog shiftId={shiftId} open={dialog === "credit"} busy={edit.isPending} onClose={() => setDialog(null)} onSave={(body) => run({ kind: "add-credit", ...body }, () => setDialog(null))} />
          <ArDialog open={dialog === "ar"} busy={edit.isPending} onClose={() => setDialog(null)} onSave={(body) => run({ kind: "add-ar", ...body }, () => setDialog(null))} />
          <ExpenseDialog open={dialog === "expense"} busy={edit.isPending} onClose={() => setDialog(null)} onSave={(body) => run({ kind: "add-expense", ...body }, () => setDialog(null))} />
          <ConfirmDialog
            open={removing !== null}
            title={T.remove}
            message={
              <>
                <b>{removing?.label}</b>
                <br />
                {T.removeConfirm}
              </>
            }
            confirmLabel={T.remove}
            variant="danger"
            loading={edit.isPending}
            onCancel={() => setRemoving(null)}
            onConfirm={() => {
              if (!removing) return;
              const payload =
                removing.kind === "remove-credit"
                  ? { kind: "remove-credit" as const, sale_id: removing.id }
                  : removing.kind === "remove-ar"
                    ? { kind: "remove-ar" as const, payment_id: removing.id }
                    : { kind: "remove-expense" as const, expense_id: removing.id };
              run(payload, () => setRemoving(null));
            }}
          />
        </>
      ) : null}
    </Card>
  );
}

// --------------------------------------------------------------------------
// Засварын цонхнууд
// --------------------------------------------------------------------------
function DialogFooter({ busy, disabled, onClose, onSave }: { busy: boolean; disabled?: boolean; onClose: () => void; onSave: () => void }) {
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

function TendersDialog({
  open,
  view,
  busy,
  onClose,
  onSave,
}: {
  open: boolean;
  view: ClosingView;
  busy: boolean;
  onClose: () => void;
  onSave: (body: { declared_cash: string; settlement_total: string; transfer_total: string; note?: string }) => void;
}) {
  const [ready, setReady] = useState(false);
  const [declared, setDeclared] = useState("");
  const [settlement, setSettlement] = useState("");
  const [transfer, setTransfer] = useState("");
  const [note, setNote] = useState("");
  if (open && !ready) {
    setReady(true);
    setDeclared(view.declared_cash);
    setSettlement(view.settlement_total);
    setTransfer(view.transfer_total);
    setNote("");
  }
  if (!open && ready) setReady(false);
  return (
    <Modal open={open} onClose={onClose} size="md" title={T.tendersTitle} footer={<DialogFooter busy={busy} onClose={onClose} onSave={() => onSave({ declared_cash: declared || "0", settlement_total: settlement || "0", transfer_total: transfer || "0", note })} />}>
      <div className="flex flex-col gap-4">
        <NumberField name="fix-declared" label={t.shift.declaredCash} value={declared} onChange={setDeclared} suffix={t.units.mnt} />
        <NumberField name="fix-settlement" label={T.methodCard} value={settlement} onChange={setSettlement} suffix={t.units.mnt} />
        <NumberField name="fix-transfer" label={T.methodTransfer} value={transfer} onChange={setTransfer} suffix={t.units.mnt} />
        <TextField label={T.description} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

function TargetFields({ value, onChange, name, onName, phone, onPhone, enabled }: { value: string; onChange: (v: string) => void; name: string; onName: (v: string) => void; phone: string; onPhone: (v: string) => void; enabled: boolean }) {
  const options = useTargetOptions(enabled);
  return (
    <>
      <PickerField label={T.customer} value={value} options={options} onChange={onChange} />
      {value === NEW ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label={T.newName} value={name} onChange={onName} />
          <TextField kind="tel" label={T.newPhone} value={phone} onChange={onPhone} />
        </div>
      ) : null}
    </>
  );
}

function CreditDialog({
  shiftId,
  open,
  busy,
  onClose,
  onSave,
}: {
  shiftId: UUID;
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onSave: (body: { target: ClosingTarget; fuel_id: UUID; qty?: string; amount?: string }) => void;
}) {
  const fuels = useClosingFuels(shiftId, open);
  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [fuelId, setFuelId] = useState("");
  const [mode, setMode] = useState<"amount" | "liters">("amount");
  const [value, setValue] = useState("");
  const resolved = toTarget(target, name, phone);
  const fuelOptions = (fuels.data ?? []).map((f) => ({
    value: f.fuel_id,
    label: f.name,
    hint: `${T.available}: ${formatLiters(f.liters, 2)} · ${formatMoneyExact(f.amount)}`,
  }));
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={T.creditTitle}
      footer={
        <DialogFooter
          busy={busy}
          disabled={!resolved || fuelId === "" || dToQty(value) <= 0}
          onClose={onClose}
          onSave={() => resolved && onSave({ target: resolved, fuel_id: fuelId, ...(mode === "amount" ? { amount: value } : { qty: value }) })}
        />
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{T.creditHint}</p>
        <TargetFields value={target} onChange={setTarget} name={name} onName={setName} phone={phone} onPhone={setPhone} enabled={open} />
        <PickerField label={T.fuel} value={fuelId} options={fuelOptions} onChange={setFuelId} searchable={false} />
        <PickerField
          label={T.method}
          value={mode}
          options={[
            { value: "amount", label: T.byAmount },
            { value: "liters", label: T.byLiters },
          ]}
          onChange={(v) => setMode(v as "amount" | "liters")}
          searchable={false}
        />
        <NumberField
          name="credit-value"
          label={mode === "amount" ? T.amount : T.liters}
          value={value}
          onChange={setValue}
          suffix={mode === "amount" ? t.units.mnt : t.units.liter}
          maxDecimals={mode === "amount" ? 2 : 3}
        />
      </div>
    </Modal>
  );
}

function ArDialog({ open, busy, onClose, onSave }: { open: boolean; busy: boolean; onClose: () => void; onSave: (body: { target: ClosingTarget; amount: string; method: ClosingMethod }) => void }) {
  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<ClosingMethod>("cash");
  const resolved = toTarget(target, name, phone);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={T.arTitle}
      footer={<DialogFooter busy={busy} disabled={!resolved || dToQty(amount) <= 0} onClose={onClose} onSave={() => resolved && onSave({ target: resolved, amount, method })} />}
    >
      <div className="flex flex-col gap-4">
        <TargetFields value={target} onChange={setTarget} name={name} onName={setName} phone={phone} onPhone={setPhone} enabled={open} />
        <NumberField name="ar-amount" label={T.amount} value={amount} onChange={setAmount} suffix={t.units.mnt} />
        <PickerField label={T.method} value={method} options={METHOD_OPTIONS} onChange={(v) => setMethod(v as ClosingMethod)} searchable={false} />
      </div>
    </Modal>
  );
}

function ExpenseDialog({ open, busy, onClose, onSave }: { open: boolean; busy: boolean; onClose: () => void; onSave: (body: { account_code: string; amount: string; method: ClosingMethod; description?: string }) => void }) {
  const categories = useExpenseCategories();
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<ClosingMethod>("cash");
  const [description, setDescription] = useState("");
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={T.expenseTitle}
      footer={<DialogFooter busy={busy} disabled={account === "" || dToQty(amount) <= 0} onClose={onClose} onSave={() => onSave({ account_code: account, amount, method, description })} />}
    >
      <div className="flex flex-col gap-4">
        <PickerField label={T.category} value={account} options={(categories.data ?? []).map((c) => ({ value: c.code, label: c.name_mn, hint: c.code }))} onChange={setAccount} />
        <NumberField name="expense-amount" label={T.amount} value={amount} onChange={setAmount} suffix={t.units.mnt} />
        <PickerField label={T.method} value={method} options={METHOD_OPTIONS} onChange={(v) => setMethod(v as ClosingMethod)} searchable={false} />
        <TextField label={T.description} value={description} onChange={setDescription} />
      </div>
    </Modal>
  );
}

export default ClosingWindow;
