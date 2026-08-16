import { useMemo, useRef, useState } from "react";
import { FileDown, FileText, Filter, Paperclip, Pencil, Plus, Trash2, Users, X } from "lucide-react";

import { api, errorMessage } from "../../api/client";
import {
  useContracts,
  useCreateContractMutation,
  useCreateCustomerMutation,
  useCustomers,
  useDeleteContractFileMutation,
  useUpdateCustomerMutation,
  useUploadContractFileMutation,
} from "../../api/queries/partners";
import type { Contract, Customer, CustomerType, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { InitialsAvatar } from "../../components/ui/InitialsAvatar";
import { Modal } from "../../components/ui/Modal";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { CONTRACT_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dToNumber } from "../../lib/decimal";
import { formatDate, formatMNT } from "../../lib/format";
import { districtsOf, MN_PROVINCES } from "../../lib/mnLocations";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  DateField,
  KeyValue,
  NumberField,
  Pager,
  PickerField,
  SearchInput,
  TextField,
  ToggleField,
} from "../catalog/_shared";

type TypeFilter = "all" | CustomerType;

interface CustomerForm {
  last_name: string;
  name: string;
  register_no: string;
  phone: string;
  phone2: string;
  email: string;
  province: string;
  district: string;
  credit_limit: string;
  type: CustomerType;
  is_active: boolean;
}

const EMPTY_FORM: CustomerForm = {
  last_name: "",
  name: "",
  register_no: "",
  phone: "",
  phone2: "",
  email: "",
  province: "",
  district: "",
  credit_limit: "",
  type: "b2b",
  is_active: true,
};

function locationOf(customer: Customer): string {
  if (!customer.province) return "—";
  return customer.district ? `${customer.province} · ${customer.district}` : customer.province;
}

export function CustomersPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  // --- Шүүлтүүд (erxes-маягийн зүүн самбар) — бүгд сервер талд ---
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [province, setProvince] = useState("");
  const [district, setDistrict] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Customer | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [contractOpen, setContractOpen] = useState(false);
  const [contractNo, setContractNo] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [discount, setDiscount] = useState("");
  const [billingDay, setBillingDay] = useState("1");
  const [contractError, setContractError] = useState<string | null>(null);

  const hasFilters =
    query !== "" || typeFilter !== "all" || province !== "" || district !== "" ||
    createdFrom !== "" || createdTo !== "";

  const clearFilters = (): void => {
    setQuery("");
    setTypeFilter("all");
    setProvince("");
    setDistrict("");
    setCreatedFrom("");
    setCreatedTo("");
    setOffset(0);
  };

  const customersQuery = useCustomers({
    q: query || undefined,
    type: typeFilter === "all" ? undefined : typeFilter,
    province: province || undefined,
    district: district || undefined,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
    limit: 500,
  });
  const contractsQuery = useContracts({ limit: 200 });
  const createMutation = useCreateCustomerMutation();
  const updateMutation = useUpdateCustomerMutation();
  const createContractMutation = useCreateContractMutation();
  const uploadMutation = useUploadContractFileMutation();
  const deleteFileMutation = useDeleteContractFileMutation();

  const allCustomers = useMemo(() => customersQuery.data?.items ?? [], [customersQuery.data]);
  const allContracts = useMemo(() => contractsQuery.data?.items ?? [], [contractsQuery.data]);
  const rows = useMemo(() => allCustomers.slice(offset, offset + PAGE_SIZE), [allCustomers, offset]);

  const contractsByCustomer = useMemo(() => {
    const map = new Map<string, Contract[]>();
    for (const contract of allContracts) {
      const list = map.get(contract.customer_id) ?? [];
      list.push(contract);
      map.set(contract.customer_id, list);
    }
    return map;
  }, [allContracts]);

  const provinceOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...MN_PROVINCES.map((item) => ({ value: item.name, label: item.name })),
    ],
    [],
  );
  const districtOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...districtsOf(province).map((name) => ({ value: name, label: name })),
    ],
    [province],
  );
  const formDistrictOptions = useMemo(
    () => districtsOf(form.province).map((name) => ({ value: name, label: name })),
    [form.province],
  );

  const openForm = (customer: Customer | null): void => {
    setEditing(customer);
    setFormError(null);
    setPdfFile(null);
    setForm(
      customer
        ? {
            last_name: customer.last_name ?? "",
            name: customer.name,
            register_no: customer.register_no ?? "",
            phone: customer.phone ?? "",
            phone2: customer.phone2 ?? "",
            email: customer.email ?? "",
            province: customer.province ?? "",
            district: customer.district ?? "",
            credit_limit: dToNumber(customer.credit_limit) > 0 ? customer.credit_limit : "",
            type: customer.type === "individual" ? "individual" : "b2b",
            is_active: customer.is_active,
          }
        : EMPTY_FORM,
    );
    setFormOpen(true);
  };

  /** Хадгалсны дараа сонгосон PDF-ийг хавсаргана (заавал биш). */
  const uploadIfPicked = (customerId: UUID, done: () => void): void => {
    if (!pdfFile) {
      done();
      return;
    }
    uploadMutation.mutate(
      { id: customerId, file: pdfFile },
      {
        onSuccess: done,
        onError: (error) => {
          // Карт хадгалагдсан ч файл хавсрахад алдаа гарвал хэлнэ.
          toastError(errorMessage(error));
          done();
        },
      },
    );
  };

  const submitForm = (): void => {
    setFormError(null);
    const payload = {
      last_name: form.last_name.trim() || null,
      name: form.name.trim(),
      register_no: form.register_no.trim() || null,
      phone: form.phone.trim() || null,
      phone2: form.phone2.trim() || null,
      email: form.email.trim() || null,
      province: form.province || null,
      district: form.district || null,
      credit_limit: form.credit_limit === "" ? "0" : form.credit_limit,
      type: form.type,
      is_active: form.is_active,
    };
    const finish = (): void => {
      toastSuccess(t.common.saved);
      setFormOpen(false);
    };
    const onError = (error: unknown): void => setFormError(errorMessage(error));

    if (editing) {
      updateMutation.mutate(
        { id: editing.id, payload },
        { onSuccess: (updated) => uploadIfPicked(updated.id, finish), onError },
      );
    } else {
      createMutation.mutate(payload, {
        onSuccess: (created) => uploadIfPicked(created.id, finish),
        onError,
      });
    }
  };

  const submitContract = (): void => {
    if (!selected || contractNo.trim() === "") return;
    setContractError(null);
    createContractMutation.mutate(
      {
        customer_id: selected.id,
        contract_no: contractNo.trim(),
        credit_limit: creditLimit === "" ? "0" : creditLimit,
        price_discount_per_l: discount === "" ? "0" : discount,
        billing_day: Math.min(28, Math.max(1, Math.round(dToNumber(billingDay)) || 1)),
        status: "active",
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setContractOpen(false);
          setContractNo("");
          setCreditLimit("");
          setDiscount("");
        },
        onError: (error) => setContractError(errorMessage(error)),
      },
    );
  };

  const downloadPdf = (customer: Customer): void => {
    void api
      .download(`/api/customers/${customer.id}/contract-file`, undefined, `geree-${customer.name}.pdf`)
      .catch((error: unknown) => toastError(errorMessage(error)));
  };

  const columns: Column<Customer>[] = [
    {
      key: "name",
      header: t.common.name,
      primary: true,
      render: (row) => (
        <span className="flex items-center gap-3">
          <InitialsAvatar name={`${row.last_name ?? ""} ${row.name}`.trim()} seed={row.id} />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold text-ink">{row.full_name}</span>
            <span className="text-xs text-ink-soft">
              {row.type_name}
              {row.register_no ? ` · ${row.register_no}` : ""}
            </span>
          </span>
        </span>
      ),
    },
    {
      key: "location",
      header: t.partners.location,
      render: (row) => <span className="text-ink-soft">{locationOf(row)}</span>,
    },
    { key: "phone", header: t.partners.phone1, numeric: true, render: (row) => row.phone ?? "—" },
    {
      key: "phone2",
      header: t.partners.phone2,
      numeric: true,
      hideOnMobile: true,
      render: (row) => row.phone2 ?? "—",
    },
    {
      key: "email",
      header: t.common.email,
      hideOnMobile: true,
      render: (row) => row.email ?? "—",
    },
    {
      key: "credit_limit",
      header: t.partners.creditLimit,
      align: "right",
      numeric: true,
      render: (row) =>
        dToNumber(row.credit_limit) > 0 ? (
          <span className="font-bold">{formatMNT(row.credit_limit)}</span>
        ) : (
          "—"
        ),
    },
    {
      key: "contract_pdf",
      header: t.partners.contract,
      align: "center",
      hideOnMobile: true,
      render: (row) =>
        row.has_contract_file ? (
          <Button
            variant="ghost"
            size="md"
            icon={<FileDown />}
            onClick={(event) => {
              event.stopPropagation();
              downloadPdf(row);
            }}
          >
            PDF
          </Button>
        ) : (
          <span className="text-ink-faint">—</span>
        ),
    },
    {
      key: "created_at",
      header: t.common.createdAt,
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatDate(row.created_at),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      hideOnMobile: true,
      render: (row) => (
        <Button
          variant="secondary"
          size="md"
          icon={<Pencil />}
          onClick={(event) => {
            event.stopPropagation();
            openForm(row);
          }}
        >
          {t.common.edit}
        </Button>
      ),
    },
  ];

  const selectedContracts = selected ? (contractsByCustomer.get(selected.id) ?? []) : [];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.partners.customers}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
            {t.partners.newCustomer}
          </Button>
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
            <ChipGroup<TypeFilter>
              label={t.partners.type}
              value={typeFilter}
              onChange={(next) => {
                setTypeFilter(next);
                setOffset(0);
              }}
              options={[
                { value: "all", label: t.common.all },
                { value: "b2b", label: t.partners.b2b },
                { value: "individual", label: t.partners.individual },
              ]}
            />
            <PickerField
              label={t.partners.province}
              value={province}
              options={provinceOptions}
              onChange={(next) => {
                setProvince(next);
                setDistrict("");
                setOffset(0);
              }}
            />
            <PickerField
              label={t.partners.district}
              value={district}
              options={districtOptions}
              onChange={(next) => {
                setDistrict(next);
                setOffset(0);
              }}
              disabled={province === ""}
            />
            <div className="flex flex-col gap-3">
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
              {t.common.total}: <b className="num text-ink">{customersQuery.data?.total ?? 0}</b>
            </p>
          </div>
        </Card>

        {/* Жагсаалт */}
        <div className="flex min-w-0 flex-col gap-6">
          <Card flush>
            <DataTable
              columns={columns}
              rows={rows}
              rowKey={(row) => row.id}
              onRowClick={setSelected}
              loading={customersQuery.isLoading}
              empty={
                <EmptyState
                  icon={hasFilters ? <Filter className="h-7 w-7" /> : <Users className="h-7 w-7" />}
                  title={t.common.empty}
                  hint={t.common.emptyHint}
                  action={
                    hasFilters ? (
                      <Button variant="secondary" size="md" onClick={clearFilters}>
                        {t.partners.clearFilters}
                      </Button>
                    ) : (
                      <Button variant="primary" size="md" onClick={() => openForm(null)}>
                        {t.partners.newCustomer}
                      </Button>
                    )
                  }
                />
              }
              footer={
                <Pager
                  offset={offset}
                  limit={PAGE_SIZE}
                  total={allCustomers.length}
                  onChange={setOffset}
                />
              }
            />
          </Card>

          {selected ? (
            <Card
              title={selected.full_name}
              subtitle={locationOf(selected)}
              actions={
                <>
                  <Button variant="primary" size="md" icon={<FileText />} onClick={() => setContractOpen(true)}>
                    {t.partners.newContract}
                  </Button>
                  <Button variant="ghost" size="md" onClick={() => setSelected(null)}>
                    {t.common.close}
                  </Button>
                </>
              }
            >
              <div className="flex flex-col gap-5">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <KeyValue label={t.common.registerNo} value={selected.register_no ?? "—"} numeric />
                  <KeyValue label={t.partners.phone1} value={selected.phone ?? "—"} numeric />
                  <KeyValue label={t.partners.phone2} value={selected.phone2 ?? "—"} numeric />
                  <KeyValue label={t.common.email} value={selected.email ?? "—"} />
                  <KeyValue
                    label={t.partners.creditLimitContract}
                    value={formatMNT(selected.credit_limit)}
                    numeric
                  />
                  <KeyValue
                    label={t.partners.contractPdf}
                    value={
                      selected.has_contract_file ? (
                        <Button
                          variant="ghost"
                          size="md"
                          icon={<FileDown />}
                          onClick={() => downloadPdf(selected)}
                        >
                          {t.partners.viewPdf}
                        </Button>
                      ) : (
                        "—"
                      )
                    }
                  />
                  <KeyValue label={t.common.createdAt} value={formatDate(selected.created_at)} numeric />
                  <KeyValue
                    label={t.common.status}
                    value={
                      <StatusBadge
                        size="sm"
                        tone={selected.is_active ? "success" : "neutral"}
                        label={selected.is_active ? t.common.active : t.common.inactive}
                      />
                    }
                  />
                </div>

                {selectedContracts.length === 0 ? (
                  <EmptyState compact title={t.partners.contracts} hint={t.common.emptyHint} />
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    {selectedContracts.map((contract) => {
                      const limit = dToNumber(contract.credit_limit);
                      const used = dToNumber(contract.balance);
                      const pct = limit > 0 ? (used / limit) * 100 : 0;
                      return (
                        <div key={contract.id} className="flex flex-col gap-3 rounded-xl border border-line p-4">
                          <div className="flex items-start justify-between gap-3">
                            <span className="num text-lg font-bold text-ink">{contract.contract_no}</span>
                            <StatusBadge
                              size="sm"
                              meta={statusMeta(CONTRACT_STATUS_META, contract.status, contract.status_name)}
                            />
                          </div>
                          <ProgressBar
                            value={pct}
                            tone={pct >= 90 ? "danger" : pct >= 70 ? "warning" : "success"}
                            label={t.partners.creditLimit}
                            valueLabel={`${formatMNT(contract.balance)} / ${formatMNT(contract.credit_limit)}`}
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <KeyValue
                              label={t.partners.creditAvailable}
                              value={formatMNT(contract.credit_available)}
                              numeric
                            />
                            <KeyValue
                              label={t.partners.discountPerL}
                              value={formatMNT(contract.price_discount_per_l)}
                              numeric
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>
          ) : null}
        </div>
      </div>

      {/* Харилцагчийн карт нэмэх/засах */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="lg"
        title={editing ? t.common.edit : t.partners.newCustomer}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={form.name.trim() === ""}
              loading={createMutation.isPending || updateMutation.isPending || uploadMutation.isPending}
              onClick={submitForm}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <ChipGroup<CustomerType>
            label={t.partners.type}
            value={form.type}
            onChange={(value) => setForm({ ...form, type: value })}
            options={[
              { value: "b2b", label: t.partners.b2b },
              { value: "individual", label: t.partners.individual },
            ]}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.partners.lastName}
              value={form.last_name}
              onChange={(value) => setForm({ ...form, last_name: value })}
            />
            <TextField
              label={t.partners.firstName}
              value={form.name}
              onChange={(value) => setForm({ ...form, name: value })}
            />
            <TextField
              label={t.common.registerNo}
              value={form.register_no}
              onChange={(value) => setForm({ ...form, register_no: value })}
            />
            <TextField
              label={t.common.email}
              value={form.email}
              onChange={(value) => setForm({ ...form, email: value })}
            />
            <TextField
              label={t.partners.phone1}
              value={form.phone}
              onChange={(value) => setForm({ ...form, phone: value })}
            />
            <TextField
              label={t.partners.phone2}
              value={form.phone2}
              onChange={(value) => setForm({ ...form, phone2: value })}
            />
            <PickerField
              label={t.partners.province}
              value={form.province}
              options={MN_PROVINCES.map((item) => ({ value: item.name, label: item.name }))}
              onChange={(value) => setForm({ ...form, province: value, district: "" })}
            />
            <PickerField
              label={t.partners.district}
              value={form.district}
              options={formDistrictOptions}
              onChange={(value) => setForm({ ...form, district: value })}
              disabled={form.province === ""}
            />
          </div>
          <NumberField
            name="customer-credit-limit"
            label={t.partners.creditLimitContract}
            value={form.credit_limit}
            onChange={(value) => setForm({ ...form, credit_limit: value })}
            suffix={t.units.mnt}
          />

          {/* Гэрээний PDF — заавал биш */}
          <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-alt px-4 py-3">
            <span className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
              {t.partners.contractPdf}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
              />
              <Button
                variant="secondary"
                size="md"
                icon={<Paperclip />}
                onClick={() => fileInputRef.current?.click()}
              >
                {t.partners.attachPdf}
              </Button>
              {pdfFile ? (
                <span className="flex items-center gap-2 text-sm text-ink">
                  <b className="max-w-[14rem] truncate">{pdfFile.name}</b>
                  <button
                    type="button"
                    className="flex h-11 w-11 items-center justify-center rounded-lg text-ink-soft hover:bg-surface-sunken"
                    onClick={() => setPdfFile(null)}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </span>
              ) : editing?.has_contract_file ? (
                <>
                  <StatusBadge size="sm" tone="success" label={t.partners.pdfAttached} />
                  <Button variant="ghost" size="md" icon={<FileDown />} onClick={() => downloadPdf(editing)}>
                    {t.partners.viewPdf}
                  </Button>
                  <Button
                    variant="ghost"
                    size="md"
                    icon={<Trash2 />}
                    loading={deleteFileMutation.isPending}
                    onClick={() =>
                      deleteFileMutation.mutate(editing.id, {
                        onSuccess: () => {
                          toastSuccess(t.common.saved);
                          setEditing({ ...editing, has_contract_file: false });
                        },
                        onError: (error) => setFormError(errorMessage(error)),
                      })
                    }
                  >
                    {t.partners.removePdf}
                  </Button>
                </>
              ) : null}
            </div>
            <span className="text-xs text-ink-faint">{t.partners.pdfOptionalHint}</span>
          </div>

          <ToggleField
            label={t.common.active}
            value={form.is_active}
            onChange={(value) => setForm({ ...form, is_active: value })}
          />
          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Шинэ гэрээ (тооцооны лимит гэрээн дээрээ) */}
      <Modal
        open={contractOpen}
        onClose={() => setContractOpen(false)}
        size="md"
        title={t.partners.newContract}
        subtitle={selected?.full_name}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setContractOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={contractNo.trim() === ""}
              loading={createContractMutation.isPending}
              onClick={submitContract}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.partners.contractNo} value={contractNo} onChange={setContractNo} />
          <NumberField
            name="contract-credit-limit"
            label={t.partners.creditLimit}
            value={creditLimit}
            onChange={setCreditLimit}
            suffix={t.units.mnt}
          />
          <NumberField
            name="contract-discount"
            label={t.partners.discountPerL}
            value={discount}
            onChange={setDiscount}
            suffix={t.units.perLiter}
          />
          <NumberField
            name="contract-billing-day"
            label={t.partners.billingDay}
            value={billingDay}
            onChange={setBillingDay}
            allowDecimal={false}
          />
          {contractError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {contractError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default CustomersPage;
