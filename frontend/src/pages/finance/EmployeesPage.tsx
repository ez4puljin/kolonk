/**
 * Ажилтны бүртгэл — erxes-маягийн шүүлттэй жагсаалт + урьдчилгаа.
 *
 * Урьдчилгаа олгоход `1205 Ажилтны урьдчилгаа` дансанд авлага үүсч, цалин
 * бодох үед суутгагдан хаагдана. Бэлнээр олгосон бол ээлжийн кассаас
 * автоматаар хасагдана.
 */

import { useMemo, useState } from "react";
import { Filter, Plus, UserPlus, Users, Wallet, X } from "lucide-react";

import { useBranches } from "../../api/queries/branches";
import {
  useAdvances,
  useCreateEmployeeMutation,
  useEmployees,
  useGiveAdvanceMutation,
  useUpdateEmployeeMutation,
} from "../../api/queries/payroll";
import type { Employee, EmployeeAdvance } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Column, DataTable } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { InitialsAvatar } from "../../components/ui/InitialsAvatar";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TouchSelect } from "../../components/ui/TouchSelect";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { formatDate, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  DateField,
  Pager,
  PickerField,
  SearchInput,
  TextField,
  ToggleField,
} from "../catalog/_shared";

const PAD_SALARY = "employee.salary";
const PAD_ADVANCE = "advance.amount";

type StatusFilter = "all" | "working" | "departed";

export function EmployeesPage() {
  const [formOpen, setFormOpen] = useState(false);
  const [advanceOpen, setAdvanceOpen] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);

  // --- Шүүлтүүд (erxes-маягийн зүүн самбар) — бүгд сервер талд ---
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [branchId, setBranchId] = useState("");
  const [hiredFrom, setHiredFrom] = useState("");
  const [hiredTo, setHiredTo] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [offset, setOffset] = useState(0);

  const [fullName, setFullName] = useState("");
  const [position, setPosition] = useState("");
  const [salary, setSalary] = useState("0.00");
  const [phone, setPhone] = useState("");
  const [registerNo, setRegisterNo] = useState("");
  const [formBranchId, setFormBranchId] = useState("");
  const [siEnabled, setSiEnabled] = useState(true);
  const [hireDate, setHireDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [advEmployee, setAdvEmployee] = useState<string | null>(null);
  const [advAmount, setAdvAmount] = useState("0.00");
  const [advFrom, setAdvFrom] = useState("cash");

  const employeesQuery = useEmployees({
    search: query || undefined,
    is_active: status === "all" ? undefined : status === "working",
    branch_id: branchId || undefined,
    hired_from: hiredFrom || undefined,
    hired_to: hiredTo || undefined,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
  });
  const advancesQuery = useAdvances();
  const branchesQuery = useBranches();
  const createMutation = useCreateEmployeeMutation();
  const updateMutation = useUpdateEmployeeMutation();
  const advanceMutation = useGiveAdvanceMutation();

  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const employees = useMemo(() => employeesQuery.data?.items ?? [], [employeesQuery.data]);
  const advances = useMemo(() => advancesQuery.data?.items ?? [], [advancesQuery.data]);
  const rows = useMemo(() => employees.slice(offset, offset + PAGE_SIZE), [employees, offset]);

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const multiBranch = branches.length > 1;

  const hasFilters =
    query !== "" || status !== "all" || branchId !== "" ||
    hiredFrom !== "" || hiredTo !== "" || createdFrom !== "" || createdTo !== "";

  const clearFilters = (): void => {
    setQuery("");
    setStatus("all");
    setBranchId("");
    setHiredFrom("");
    setHiredTo("");
    setCreatedFrom("");
    setCreatedTo("");
    setOffset(0);
  };

  const resetForm = (): void => {
    setEditing(null);
    setFullName("");
    setPosition("");
    setSalary("0.00");
    setPhone("");
    setRegisterNo("");
    setFormBranchId(branches[0]?.id ?? "");
    setSiEnabled(true);
    setHireDate("");
    setEndDate("");
  };

  const openEdit = (employee: Employee): void => {
    setEditing(employee);
    setFullName(employee.full_name);
    setPosition(employee.position ?? "");
    setSalary(employee.base_salary);
    setPhone(employee.phone ?? "");
    setRegisterNo(employee.register_no ?? "");
    setFormBranchId(employee.branch_id ?? "");
    setSiEnabled(employee.si_enabled);
    setHireDate(employee.hire_date ?? "");
    setEndDate(employee.end_date ?? "");
    setFormOpen(true);
  };

  const submit = (): void => {
    const payload = {
      full_name: fullName.trim(),
      position: position.trim() || null,
      base_salary: salary,
      branch_id: formBranchId || null,
      si_enabled: siEnabled,
      phone: phone.trim() || null,
      register_no: registerNo.trim() || null,
      hire_date: hireDate || null,
      end_date: endDate || null,
    };
    const onSuccess = (): void => {
      toastSuccess(editing ? t.common.saved : t.payroll.employeeAdded);
      setFormOpen(false);
      resetForm();
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

  const submitAdvance = (): void => {
    if (!advEmployee) return;
    advanceMutation.mutate(
      { employee_id: advEmployee as Employee["id"], amount: advAmount, paid_from: advFrom },
      {
        onSuccess: () => {
          toastSuccess(t.payroll.advanceGiven);
          setAdvanceOpen(false);
          setAdvAmount("0.00");
          setAdvEmployee(null);
        },
        onError: (e: unknown) => toastError(e instanceof Error ? e.message : t.common.error),
      },
    );
  };

  const columns: Column<Employee>[] = [
    {
      key: "name",
      header: t.payroll.employee,
      primary: true,
      render: (r) => (
        <span className="flex items-center gap-3">
          <InitialsAvatar name={r.full_name} seed={r.id} />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold text-ink">{r.full_name}</span>
            <span className="truncate text-xs text-ink-soft">
              {r.position ?? "—"}
              {r.si_enabled ? "" : ` · ${t.payroll.siDisabled}`}
            </span>
          </span>
        </span>
      ),
    },
    ...(multiBranch
      ? [
          {
            key: "branch",
            header: t.branches.title,
            render: (r) => <span className="text-ink-soft">{r.branch_name ?? "—"}</span>,
          } satisfies Column<Employee>,
        ]
      : []),
    { key: "phone", header: t.common.phone, numeric: true, hideOnMobile: true, render: (r) => r.phone ?? "—" },
    {
      key: "register",
      header: t.common.registerNo,
      numeric: true,
      hideOnMobile: true,
      render: (r) => r.register_no ?? "—",
    },
    {
      key: "salary",
      header: t.payroll.baseSalary,
      render: (r) => <span className="font-bold">{formatMNT(r.base_salary)}</span>,
      align: "right",
      numeric: true,
    },
    {
      key: "period",
      header: t.payroll.employmentPeriod,
      numeric: true,
      hideOnMobile: true,
      render: (r) =>
        r.hire_date || r.end_date
          ? `${r.hire_date ? formatDate(r.hire_date) : "…"} — ${r.end_date ? formatDate(r.end_date) : "…"}`
          : "—",
    },
    {
      key: "status",
      header: t.common.status,
      render: (r) => (
        <StatusBadge
          size="sm"
          tone={r.is_active ? "success" : "neutral"}
          label={r.is_active ? t.payroll.working : t.payroll.departed}
        />
      ),
    },
  ];

  const advanceColumns: Column<EmployeeAdvance>[] = [
    { key: "date", header: t.payroll.date, render: (r) => formatDate(r.advance_date) },
    { key: "name", header: t.payroll.employee, render: (r) => r.employee_name, primary: true },
    {
      key: "amount",
      header: t.payroll.amount,
      render: (r) => formatMNT(r.amount),
      align: "right",
      numeric: true,
    },
    {
      key: "from",
      header: t.payroll.source,
      render: (r) => (r.paid_from === "cash" ? t.payroll.fromCash : t.payroll.fromBank),
      hideOnMobile: true,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.payroll.employees}
        subtitle={t.payroll.employeesSubtitle}
        actions={
          <>
            <Button variant="secondary" size="lg" icon={<Wallet />} onClick={() => setAdvanceOpen(true)}>
              {t.payroll.giveAdvance}
            </Button>
            <Button
              size="lg"
              icon={<UserPlus />}
              onClick={() => {
                resetForm();
                setFormOpen(true);
              }}
            >
              {t.payroll.addEmployee}
            </Button>
          </>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
        {/* erxes-маягийн зүүн шүүлтийн самбар */}
        <Card
          title={t.partners.filters}
          actions={
            hasFilters ? (
              <Button variant="ghost" size="md" icon={<X />} onClick={clearFilters}>
                {t.common.clear}
              </Button>
            ) : null
          }
        >
          <div className="flex flex-col gap-4">
            <SearchInput
              value={query}
              onChange={(next) => {
                setQuery(next);
                setOffset(0);
              }}
              className="w-full"
            />
            <ChipGroup<StatusFilter>
              label={t.common.status}
              value={status}
              onChange={(next) => {
                setStatus(next);
                setOffset(0);
              }}
              options={[
                { value: "all", label: t.common.all },
                { value: "working", label: t.payroll.working },
                { value: "departed", label: t.payroll.departed },
              ]}
            />
            {multiBranch ? (
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
              />
            ) : null}
            <div className="flex flex-col gap-3">
              <DateField
                label={`${t.payroll.hiredRange} — ${t.common.from}`}
                value={hiredFrom}
                max={hiredTo || undefined}
                onChange={(next) => {
                  setHiredFrom(next);
                  setOffset(0);
                }}
              />
              <DateField
                label={`${t.payroll.hiredRange} — ${t.common.to}`}
                value={hiredTo}
                min={hiredFrom || undefined}
                onChange={(next) => {
                  setHiredTo(next);
                  setOffset(0);
                }}
              />
              <DateField
                label={`${t.partners.createdRange} — ${t.common.from}`}
                value={createdFrom}
                max={createdTo || undefined}
                onChange={(next) => {
                  setCreatedFrom(next);
                  setOffset(0);
                }}
              />
              <DateField
                label={`${t.partners.createdRange} — ${t.common.to}`}
                value={createdTo}
                min={createdFrom || undefined}
                onChange={(next) => {
                  setCreatedTo(next);
                  setOffset(0);
                }}
              />
            </div>
            <p className="border-t border-line pt-3 text-sm text-ink-soft">
              {t.common.total}: <b className="num text-ink">{employeesQuery.data?.total ?? 0}</b>
            </p>
          </div>
        </Card>

        {/* Жагсаалт + урьдчилгаа */}
        <div className="flex min-w-0 flex-col gap-6">
          <Card flush>
            <DataTable
              columns={columns}
              rows={rows}
              rowKey={(r) => r.id}
              onRowClick={openEdit}
              loading={employeesQuery.isLoading}
              empty={
                <EmptyState
                  icon={hasFilters ? <Filter className="h-7 w-7" /> : <Users className="h-7 w-7" />}
                  title={t.payroll.noEmployees}
                  hint={t.common.emptyHint}
                  action={
                    hasFilters ? (
                      <Button variant="secondary" size="md" onClick={clearFilters}>
                        {t.partners.clearFilters}
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        size="md"
                        onClick={() => {
                          resetForm();
                          setFormOpen(true);
                        }}
                      >
                        {t.payroll.addEmployee}
                      </Button>
                    )
                  }
                />
              }
              footer={
                <Pager offset={offset} limit={PAGE_SIZE} total={employees.length} onChange={setOffset} />
              }
            />
          </Card>

          {advances.length > 0 ? (
            <Card title={t.payroll.advances} flush>
              <DataTable columns={advanceColumns} rows={advances} rowKey={(r) => r.id} />
            </Card>
          ) : null}
        </div>
      </div>

      {/* Ажилтан нэмэх/засах */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? t.payroll.editEmployee : t.payroll.addEmployee}
        size="md"
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.payroll.fullName} value={fullName} onChange={setFullName} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField label={t.payroll.position} value={position} onChange={setPosition} />
            {multiBranch ? (
              <PickerField
                label={t.branches.title}
                value={formBranchId}
                options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
                onChange={setFormBranchId}
              />
            ) : null}
          </div>

          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.payroll.baseSalary}
            </div>
            <button
              type="button"
              onClick={() =>
                openNumPad({
                  target: PAD_SALARY,
                  title: t.payroll.baseSalary,
                  value: salary,
                  allowDecimal: true,
                  suffix: t.units.mnt,
                })
              }
              className="flex min-h-20 w-full items-center justify-between rounded-2xl border-2 border-line-strong bg-surface-alt px-6"
            >
              <span className="text-sm text-ink-soft">{t.payroll.perMonth}</span>
              <span className="num text-2xl font-bold text-ink">{formatMNT(salary)}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField label={t.payroll.phone} value={phone} onChange={setPhone} />
            <TextField label={t.payroll.registerNo} value={registerNo} onChange={setRegisterNo} />
          </div>

          {/* Ажилд орсон/гарсан огноо — цалин сарын дундуур автоматаар хуваарилагдана */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DateField label={t.payroll.hireDate} value={hireDate} onChange={setHireDate} />
            <DateField label={t.payroll.endDate} value={endDate} onChange={setEndDate} />
          </div>
          {/* НДШ бодох эсэх — тэтгэвэрт гарсан, гэрээт ажилтанд унтраана */}
          <ToggleField
            label={t.payroll.siEnabled}
            hint={t.payroll.siHint}
            value={siEnabled}
            onChange={setSiEnabled}
          />

          <p className="rounded-xl bg-info-soft px-4 py-3 text-sm text-info-dark">
            {t.payroll.datesHint}
          </p>

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              disabled={!fullName.trim() || createMutation.isPending || updateMutation.isPending}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submit}
            >
              {t.common.save}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Урьдчилгаа олгох */}
      <Modal
        open={advanceOpen}
        onClose={() => setAdvanceOpen(false)}
        title={t.payroll.giveAdvance}
        size="md"
      >
        <div className="flex flex-col gap-4">
          <TouchSelect
            label={t.payroll.employee}
            value={advEmployee}
            onChange={setAdvEmployee}
            options={employees
              .filter((e) => e.is_active)
              .map((e) => ({ value: e.id as string, label: e.full_name }))}
            columns={2}
          />

          <button
            type="button"
            onClick={() =>
              openNumPad({
                target: PAD_ADVANCE,
                title: t.payroll.amount,
                value: advAmount,
                allowDecimal: true,
                suffix: t.units.mnt,
              })
            }
            className="flex min-h-20 w-full items-center justify-between rounded-2xl border-2 border-line-strong bg-surface-alt px-6"
          >
            <span className="text-sm text-ink-soft">{t.payroll.amount}</span>
            <span className="num text-2xl font-bold text-ink">{formatMNT(advAmount)}</span>
          </button>

          <TouchSelect
            label={t.payroll.source}
            value={advFrom}
            onChange={setAdvFrom}
            options={[
              { value: "cash", label: t.payroll.fromCash },
              { value: "bank", label: t.payroll.fromBank },
            ]}
            columns={2}
          />

          <p className="rounded-xl bg-info-soft px-4 py-3 text-sm text-info-dark">
            {t.payroll.advanceHint}
          </p>

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setAdvanceOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              icon={<Plus />}
              disabled={!advEmployee || Number(advAmount) <= 0 || advanceMutation.isPending}
              loading={advanceMutation.isPending}
              onClick={submitAdvance}
            >
              {t.payroll.giveAdvance}
            </Button>
          </div>
        </div>
      </Modal>

      <NumPadModal
        onSubmit={(target, value) => {
          if (target === PAD_SALARY) setSalary(value || "0");
          if (target === PAD_ADVANCE) setAdvAmount(value || "0");
        }}
      />
    </div>
  );
}

export default EmployeesPage;
