/**
 * Салбарын удирдлага — зөвхөн **эзэн** үүсгэж, засна.
 *
 * Түгээгч салбартаа харьяалагдаж, нэвтрэхэд салбар нь автоматаар сонгогдоно.
 * Менежер, эзэн салбаргүй — бүх салбарын мэдээллийг хардаг.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Plus, Settings2, Users } from "lucide-react";

import {
  useBranches,
  useCreateBranchMutation,
  useUpdateBranchMutation,
} from "../../api/queries/branches";
import type { Branch } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Column, DataTable } from "../../components/ui/DataTable";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { useUiStore } from "../../stores/ui";
import { TextField } from "../catalog/_shared";

export function BranchesPage() {
  const navigate = useNavigate();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [active, setActive] = useState(true);

  const branchesQuery = useBranches();
  const createMutation = useCreateBranchMutation();
  const updateMutation = useUpdateBranchMutation();

  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const branches = branchesQuery.data ?? [];
  const activeCount = branches.filter((b) => b.is_active).length;
  const staffCount = branches.reduce((sum, b) => sum + b.user_count, 0);

  const reset = (): void => {
    setEditing(null);
    setCode("");
    setName("");
    setAddress("");
    setPhone("");
    setActive(true);
  };

  const openEdit = (branch: Branch): void => {
    setEditing(branch);
    setCode(branch.code);
    setName(branch.name);
    setAddress(branch.address ?? "");
    setPhone(branch.phone ?? "");
    setActive(branch.is_active);
    setFormOpen(true);
  };

  const submit = (): void => {
    const payload = {
      code: code.trim(),
      name: name.trim(),
      address: address.trim() || null,
      phone: phone.trim() || null,
      is_active: active,
    };
    const onSuccess = (): void => {
      toastSuccess(editing ? t.common.saved : t.branches.created);
      setFormOpen(false);
      reset();
    };
    const onError = (e: unknown): void => {
      toastError(e instanceof Error ? e.message : t.common.error);
    };

    if (editing) {
      updateMutation.mutate({ id: editing.id, ...payload }, { onSuccess, onError });
    } else {
      createMutation.mutate(payload, { onSuccess, onError });
    }
  };

  const columns: Column<Branch>[] = [
    { key: "code", header: t.branches.code, render: (r) => r.code, width: "6rem" },
    { key: "name", header: t.branches.name, render: (r) => r.name, primary: true },
    { key: "address", header: t.branches.address, render: (r) => r.address ?? "—", hideOnMobile: true },
    { key: "phone", header: t.branches.phone, render: (r) => r.phone ?? "—", hideOnMobile: true },
    {
      key: "users",
      header: t.branches.staff,
      render: (r) => r.user_count,
      align: "right",
      numeric: true,
    },
    {
      key: "shifts",
      header: t.branches.openShifts,
      render: (r) =>
        r.open_shifts > 0 ? (
          <StatusBadge tone="success" label={String(r.open_shifts)} />
        ) : (
          "—"
        ),
      align: "right",
      hideOnMobile: true,
    },
    {
      key: "status",
      header: t.common.status,
      render: (r) => (
        <StatusBadge
          tone={r.is_active ? "success" : "neutral"}
          label={r.is_active ? t.common.active : t.common.inactive}
        />
      ),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (r) => (
        <Button
          variant="secondary"
          size="md"
          icon={<Settings2 />}
          onClick={(event) => {
            event.stopPropagation();
            navigate(`/branches/${r.id}`);
          }}
        >
          {t.branches.setup}
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t.branches.title}</h1>
          <p className="text-sm text-ink-soft">{t.branches.subtitle}</p>
        </div>
        <Button
          size="lg"
          icon={<Plus />}
          onClick={() => {
            reset();
            setFormOpen(true);
          }}
        >
          {t.branches.add}
        </Button>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatBox label={t.branches.total} value={branches.length} icon={<Building2 />} size="lg" />
        <StatBox label={t.branches.activeCount} value={activeCount} tone="success" />
        <StatBox label={t.branches.staff} value={staffCount} icon={<Users />} />
      </div>

      <DataTable
        columns={columns}
        rows={branches}
        rowKey={(r) => r.id}
        onRowClick={openEdit}
        loading={branchesQuery.isLoading}
        emptyTitle={t.branches.empty}
      />

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? t.branches.edit : t.branches.add}
        size="md"
      >
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <TextField label={t.branches.code} value={code} onChange={setCode} placeholder="02" />
            <div className="sm:col-span-2">
              <TextField
                label={t.branches.name}
                value={name}
                onChange={setName}
                placeholder="Цагаан-Уул салбар"
              />
            </div>
          </div>
          <TextField label={t.branches.address} value={address} onChange={setAddress} />
          <TextField label={t.branches.phone} value={phone} onChange={setPhone} />

          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-line bg-surface px-4">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="h-6 w-6 accent-action"
            />
            <span className="text-sm font-medium text-ink">{t.branches.isActive}</span>
          </label>

          {editing && editing.user_count > 0 && active === false ? (
            <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning-dark">
              {t.branches.deactivateWarning}
            </p>
          ) : null}

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              disabled={!code.trim() || !name.trim()}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submit}
            >
              {t.common.save}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default BranchesPage;
