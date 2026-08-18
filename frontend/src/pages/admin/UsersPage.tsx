import { useEffect, useMemo, useState } from "react";
import { Check, KeyRound, Pencil, Plus, Power, ShieldCheck, UserCog } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useCreateUserMutation,
  useDeactivateUserMutation,
  usePermissionCatalog,
  useResetPinMutation,
  useRoles,
  useSetRolePermissionsMutation,
  useUpdateUserMutation,
  useUsers,
} from "../../api/queries/users";
import type { User } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { useBranches } from "../../api/queries/branches";
import { PinPad } from "../../components/ui/PinPad";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar } from "../../components/ui/TabBar";
import { t } from "../../i18n/mn";
import { PAGE_SIZE, ROLE_META } from "../../lib/constants";
import { formatDateTime } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  Pager,
  PickerField,
  SearchInput,
  TextField,
  useDebounced,
} from "../catalog/_shared";

type ActiveFilter = "all" | "active" | "inactive";

interface UserForm {
  username: string;
  full_name: string;
  phone: string;
  role_id: string;
  branch_id: string;
}

const EMPTY_FORM: UserForm = { username: "", full_name: "", phone: "", role_id: "", branch_id: "" };

export function UsersPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [offset, setOffset] = useState(0);
  const debouncedQuery = useDebounced(query);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState<UserForm>(EMPTY_FORM);
  const [pin, setPin] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [pinTarget, setPinTarget] = useState<User | null>(null);
  const [pinError, setPinError] = useState<string | null>(null);

  const [deactivating, setDeactivating] = useState<User | null>(null);

  const branchesQuery = useBranches();
  const [roleId, setRoleId] = useState<string>("");
  const [rolePerms, setRolePerms] = useState<string[]>([]);

  const [branchFilter, setBranchFilter] = useState("");
  const usersQuery = useUsers({
    q: debouncedQuery || undefined,
    is_active: activeFilter === "all" ? undefined : activeFilter === "active",
    branch_id: branchFilter || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const rolesQuery = useRoles();
  const permissionsQuery = usePermissionCatalog();

  const createMutation = useCreateUserMutation();
  const updateMutation = useUpdateUserMutation();
  const deactivateMutation = useDeactivateUserMutation();
  const resetPinMutation = useResetPinMutation();
  const setRolePermsMutation = useSetRolePermissionsMutation();

  const users = useMemo(() => usersQuery.data?.items ?? [], [usersQuery.data]);
  const total = usersQuery.data?.total ?? 0;
  const roles = useMemo(() => rolesQuery.data?.items ?? [], [rolesQuery.data]);
  const groups = useMemo(() => permissionsQuery.data?.groups ?? [], [permissionsQuery.data]);

  const branchOptions = (branchesQuery.data ?? [])
    .filter((b) => b.is_active)
    .map((b) => ({ value: b.id as string, label: `${b.code} — ${b.name}` }));
  const selectedRole = roles.find((role) => role.id === roleId) ?? null;
  // Маягтад сонгогдсон дүр — түгээгч бол салбар ЗААВАЛ.
  const formRole = roles.find((role) => role.id === form.role_id) ?? null;
  const needsBranch = formRole?.code === "cashier";

  // Дүр сонгогдоход тухайн дүрийн эрхийн жагсаалтыг ачаална.
  useEffect(() => {
    if (roles.length === 0) return;
    const current = roles.find((role) => role.id === roleId) ?? roles[0];
    if (roleId !== current.id) setRoleId(current.id);
    setRolePerms(current.permissions);
  }, [roles, roleId]);

  const roleOptions = useMemo(
    () => roles.map((role) => ({ value: role.id, label: role.name_mn, hint: role.code })),
    [roles],
  );

  const openForm = (user: User | null): void => {
    setEditing(user);
    setPin("");
    setFormError(null);
    setForm(
      user
        ? {
            username: user.username,
            full_name: user.full_name,
            phone: user.phone ?? "",
            role_id: user.role_id,
            branch_id: user.branch_id ?? "",
          }
        : { ...EMPTY_FORM, role_id: roles[0]?.id ?? "" },
    );
    setFormOpen(true);
  };

  const submitForm = (): void => {
    setFormError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setFormOpen(false);
    };
    const onError = (error: unknown): void => setFormError(errorMessage(error));

    if (editing) {
      updateMutation.mutate(
        {
          id: editing.id,
          payload: {
            username: form.username.trim(),
            full_name: form.full_name.trim(),
            phone: form.phone.trim() || null,
            role_id: form.role_id,
            branch_id: form.branch_id || null,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createMutation.mutate(
        {
          username: form.username.trim(),
          full_name: form.full_name.trim(),
          phone: form.phone.trim() || null,
          role_id: form.role_id,
          branch_id: form.branch_id || null,
          pin,
        },
        { onSuccess, onError },
      );
    }
  };

  const submitPin = (value: string): void => {
    if (!pinTarget) return;
    setPinError(null);
    resetPinMutation.mutate(
      { id: pinTarget.id, pin: value },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setPinTarget(null);
        },
        onError: (error) => setPinError(errorMessage(error)),
      },
    );
  };

  const togglePermission = (code: string): void => {
    setRolePerms((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  };

  const saveRolePermissions = (): void => {
    if (!selectedRole) return;
    setRolePermsMutation.mutate(
      { roleId: selectedRole.id, codes: rolePerms },
      {
        onSuccess: () => toastSuccess(t.common.saved),
      },
    );
  };

  const columns: Column<User>[] = [
    {
      key: "full_name",
      header: t.admin.fullName,
      primary: true,
      render: (row) => <span className="font-semibold">{row.full_name}</span>,
    },
    { key: "username", header: t.admin.username, numeric: true, render: (row) => row.username },
    {
      key: "role",
      header: t.common.role,
      render: (row) => (
        <StatusBadge
          size="sm"
          tone={row.role_code === "owner" ? "warning" : row.role_code === "manager" ? "action" : "success"}
          label={row.role_name_mn || ROLE_META[row.role_code]?.label || row.role_code}
        />
      ),
    },
    { key: "phone", header: t.common.phone, numeric: true, render: (row) => row.phone ?? "—" },
    {
      key: "last_login",
      header: t.admin.lastLogin,
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatDateTime(row.last_login_at),
    },
    {
      key: "is_active",
      header: t.common.status,
      render: (row) => (
        <StatusBadge
          size="sm"
          tone={row.is_active ? "success" : "neutral"}
          label={row.is_active ? t.common.active : t.common.inactive}
        />
      ),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" size="md" icon={<Pencil />} onClick={() => openForm(row)}>
            {t.common.edit}
          </Button>
          <Button
            variant="secondary"
            size="md"
            icon={<KeyRound />}
            onClick={() => {
              setPinTarget(row);
              setPinError(null);
            }}
          >
            {t.admin.resetPin}
          </Button>
          {row.is_active ? (
            <Button variant="ghost" size="md" icon={<Power />} onClick={() => setDeactivating(row)}>
              {t.admin.deactivate}
            </Button>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.admin.users}
        icon={<UserCog className="h-6 w-6" />}
        iconTone="danger"
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
            {t.admin.newUser}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.admin.users} value={total} tone="neutral" />
        <StatBox label={t.admin.roles} value={roles.length} tone="action" />
        <StatBox
          label={t.admin.permissions}
          value={permissionsQuery.data?.total ?? 0}
          tone="neutral"
        />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
        />
        <ChipGroup<ActiveFilter>
          value={activeFilter}
          onChange={(next) => {
            setActiveFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "active", label: t.common.active },
            { value: "inactive", label: t.common.inactive },
          ]}
        />
        {/* Салбараар ангилах — түгээгчид салбартаа харьяалагдана */}
        {branches.length > 1 ? (
          <PickerField
            label={t.branches.title}
            value={branchFilter}
            options={[
              { value: "", label: t.branches.allBranches },
              ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
            ]}
            onChange={(next) => {
              setBranchFilter(next);
              setOffset(0);
            }}
            className="min-w-[12rem]"
          />
        ) : null}
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={users}
          rowKey={(row) => row.id}
          loading={usersQuery.isLoading}
          empty={
            <EmptyState icon={<UserCog className="h-7 w-7" />} title={t.common.empty} hint={t.common.emptyHint} />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      <Card
        title={t.admin.editPermissions}
        subtitle={selectedRole ? `${selectedRole.name_mn} · ${selectedRole.user_count} ${t.admin.userCount}` : ""}
        actions={
          <Button
            variant="primary"
            size="md"
            icon={<ShieldCheck />}
            loading={setRolePermsMutation.isPending}
            disabled={!selectedRole}
            onClick={saveRolePermissions}
          >
            {t.common.save}
          </Button>
        }
      >
        <div className="flex flex-col gap-5">
          <TabBar<string>
            value={roleId}
            onChange={(next) => {
              setRoleId(next);
              const role = roles.find((item) => item.id === next);
              setRolePerms(role?.permissions ?? []);
            }}
            items={roles.map((role) => ({ value: role.id, label: role.name_mn }))}
          />

          {groups.length === 0 ? (
            <EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {groups.map((group) => (
                <div key={group.key} className="flex flex-col gap-2 rounded-xl border border-line p-4">
                  <div className="text-sm font-bold text-ink">{group.name_mn}</div>
                  <div className="flex flex-col gap-1.5">
                    {group.items.map((permission) => {
                      const checked = rolePerms.includes(permission.code);
                      return (
                        <button
                          key={permission.code}
                          type="button"
                          onClick={() => togglePermission(permission.code)}
                          className={[
                            "flex min-h-12 items-center gap-3 rounded-lg border px-3 text-left transition-colors",
                            checked
                              ? "border-success/40 bg-success-soft"
                              : "border-line bg-white hover:bg-surface-alt",
                          ].join(" ")}
                        >
                          <span
                            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border ${checked ? "border-success bg-success text-white" : "border-line-strong bg-white"}`}
                          >
                            {checked ? <Check className="h-4 w-4" /> : null}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-semibold text-ink">
                              {permission.name_mn}
                            </span>
                            <span className="block truncate text-xs text-ink-faint">{permission.code}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editing ? t.common.edit : t.admin.newUser}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={
                form.username.trim() === "" ||
                form.full_name.trim() === "" ||
                form.role_id === "" ||
                (needsBranch && form.branch_id === "") ||
                (!editing && pin.length < 4)
              }
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submitForm}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label={t.admin.fullName}
            value={form.full_name}
            onChange={(value) => setForm({ ...form, full_name: value })}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.admin.username}
              value={form.username}
              onChange={(value) => setForm({ ...form, username: value })}
            />
            <TextField
              label={t.common.phone}
              value={form.phone}
              onChange={(value) => setForm({ ...form, phone: value })}
            />
          </div>
          <PickerField
            label={t.common.role}
            value={form.role_id}
            options={roleOptions}
            searchable={false}
            onChange={(value) => setForm({ ...form, role_id: value })}
          />

          {needsBranch ? (
            <PickerField
              label={t.admin.branch}
              value={form.branch_id}
              options={branchOptions}
              searchable={false}
              onChange={(value) => setForm({ ...form, branch_id: value })}
            />
          ) : (
            <p className="rounded-xl bg-info-soft px-4 py-3 text-sm text-info-dark">
              {t.admin.allBranchesHint}
            </p>
          )}

          {!editing ? (
            <div className="flex flex-col gap-3 rounded-xl bg-panel p-5">
              <span className="text-sm font-semibold text-ink-invert">{t.admin.pin}</span>
              <span className="text-xs text-ink-faint">{t.admin.pinHint}</span>
              <PinPad
                autoSubmitLength={4}
                minLength={4}
                onSubmit={(value) => setPin(value)}
                className="mx-auto"
              />
              {pin ? (
                <span className="text-center text-sm font-semibold text-success">
                  {t.admin.pin} · {"•".repeat(pin.length)}
                </span>
              ) : null}
            </div>
          ) : null}

          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={pinTarget !== null}
        onClose={() => setPinTarget(null)}
        size="sm"
        title={t.admin.resetPin}
        subtitle={pinTarget?.full_name}
      >
        <div className="flex flex-col gap-4 rounded-xl bg-panel p-5">
          <span className="text-center text-sm text-ink-faint">{t.admin.pinHint}</span>
          <PinPad
            autoSubmitLength={4}
            minLength={4}
            loading={resetPinMutation.isPending}
            error={pinError}
            onSubmit={submitPin}
            onCancel={() => setPinTarget(null)}
            className="mx-auto"
          />
        </div>
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title={t.admin.deactivate}
        message={`${t.admin.deactivateConfirm} ${deactivating?.full_name ?? ""}`}
        variant="danger"
        confirmLabel={t.admin.deactivate}
        loading={deactivateMutation.isPending}
        onConfirm={() => {
          if (!deactivating) return;
          deactivateMutation.mutate(deactivating.id, { onSettled: () => setDeactivating(null) });
        }}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}

export default UsersPage;
