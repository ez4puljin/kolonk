import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, Plus, Ticket } from "lucide-react";

import { api, errorMessage } from "../../api/client";
import { useVouchers, useVoidVoucherMutation } from "../../api/queries/instruments";
import { useCustomers } from "../../api/queries/partners";
import type { Paged, Voucher, VoucherIssueRequest, VoucherStatus } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { PAGE_SIZE, statusMeta, VOUCHER_STATUS_META } from "../../lib/constants";
import { dMul, dSum, dToNumber } from "../../lib/decimal";
import { formatDateTime, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  DateField,
  matchesQuery,
  NumberField,
  Pager,
  PickerField,
  SearchInput,
  TextAreaField,
} from "../catalog/_shared";

type StatusFilter = "all" | VoucherStatus;

export function VouchersPage() {
  const queryClient = useQueryClient();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);

  const [issueOpen, setIssueOpen] = useState(false);
  const [count, setCount] = useState("10");
  const [faceValue, setFaceValue] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [issueError, setIssueError] = useState<string | null>(null);

  const [voiding, setVoiding] = useState<Voucher | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [voidError, setVoidError] = useState<string | null>(null);

  const vouchersQuery = useVouchers({
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 500,
  });
  const customersQuery = useCustomers({ active_only: true, limit: 200 });
  const voidMutation = useVoidVoucherMutation();

  /** Сервер дээрх зам `/api/vouchers/issue-batch`. */
  const issueMutation = useMutation({
    mutationFn: (payload: VoucherIssueRequest) =>
      api.post<Paged<Voucher>>("/api/vouchers/issue-batch", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["vouchers"] });
    },
  });

  const allVouchers = useMemo(() => vouchersQuery.data?.items ?? [], [vouchersQuery.data]);
  const filtered = useMemo(
    () => allVouchers.filter((voucher) => matchesQuery([voucher.code, voucher.customer_name], query)),
    [allVouchers, query],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totals = useMemo(() => {
    const active = filtered.filter((voucher) => voucher.status === "active");
    return {
      count: filtered.length,
      activeCount: active.length,
      liability: dSum(active.map((voucher) => voucher.face_value)),
    };
  }, [filtered]);

  const customerOptions = useMemo(
    () => [
      { value: "", label: t.common.none },
      ...(customersQuery.data?.items ?? []).map((customer) => ({
        value: customer.id,
        label: customer.name,
      })),
    ],
    [customersQuery.data],
  );

  const submitIssue = (): void => {
    const total = Math.round(dToNumber(count));
    if (total <= 0 || dToNumber(faceValue) <= 0) return;
    setIssueError(null);
    issueMutation.mutate(
      {
        count: total,
        face_value: faceValue,
        expires_at: expiresAt === "" ? null : `${expiresAt}T23:59:59`,
        customer_id: customerId || null,
      },
      {
        onSuccess: (result) => {
          toastSuccess(`${t.partners.issueVouchers}: ${result.total}`);
          setIssueOpen(false);
        },
        onError: (error) => setIssueError(errorMessage(error)),
      },
    );
  };

  const submitVoid = (): void => {
    if (!voiding) return;
    setVoidError(null);
    voidMutation.mutate(
      { id: voiding.id, payload: { reason: voidReason.trim() || null } },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setVoiding(null);
          setVoidReason("");
        },
        onError: (error) => setVoidError(errorMessage(error)),
      },
    );
  };

  const columns: Column<Voucher>[] = [
    {
      key: "code",
      header: t.tender.voucherCode,
      primary: true,
      numeric: true,
      render: (row) => <span className="font-bold tracking-wider">{row.code}</span>,
    },
    {
      key: "face_value",
      header: t.partners.faceValue,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-lg font-bold">{formatMNT(row.face_value)}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(VOUCHER_STATUS_META, row.status, row.status_name)} />,
    },
    {
      key: "customer",
      header: t.partners.customer,
      render: (row) => row.customer_name ?? "—",
    },
    {
      key: "sold_at",
      header: t.partners.sellVoucher,
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.sold_at ? formatDateTime(row.sold_at) : "—"),
    },
    {
      key: "redeemed_at",
      header: t.status.redeemed,
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.redeemed_at ? formatDateTime(row.redeemed_at) : "—"),
    },
    {
      key: "expires_at",
      header: t.partners.expiresAt,
      numeric: true,
      render: (row) => (row.expires_at ? formatDateTime(row.expires_at) : "—"),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        row.status === "active" ? (
          <Button
            variant="danger"
            size="md"
            icon={<Ban />}
            onClick={() => {
              setVoiding(row);
              setVoidReason("");
              setVoidError(null);
            }}
          >
            {t.partners.voidVoucher}
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.partners.vouchers}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => setIssueOpen(true)}>
            {t.partners.issueVouchers}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.partners.vouchers} value={totals.count} tone="neutral" />
        <StatBox label={t.status.active} value={totals.activeCount} tone="success" />
        <StatBox label={t.common.balance} value={formatMNT(totals.liability)} tone="warning" />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
          placeholder={t.tender.scanVoucher}
        />
        <ChipGroup<StatusFilter>
          value={statusFilter}
          onChange={(next) => {
            setStatusFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "active", label: t.status.active },
            { value: "redeemed", label: t.status.redeemed },
            { value: "void", label: t.status.void },
            { value: "expired", label: t.status.expired },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={vouchersQuery.isLoading}
          empty={
            <EmptyState
              icon={<Ticket className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => setIssueOpen(true)}>
                  {t.partners.issueVouchers}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />}
        />
      </Card>

      <Modal
        open={issueOpen}
        onClose={() => setIssueOpen(false)}
        size="md"
        title={t.partners.issueVouchers}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setIssueOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dToNumber(count) <= 0 || dToNumber(faceValue) <= 0}
              loading={issueMutation.isPending}
              onClick={submitIssue}
            >
              {t.common.create}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <NumberField
            name="voucher-count"
            label={t.partners.voucherCount}
            value={count}
            onChange={setCount}
            allowDecimal={false}
            suffix={t.units.piece}
          />
          <NumberField
            name="voucher-face-value"
            label={t.partners.faceValue}
            value={faceValue}
            onChange={setFaceValue}
            suffix={t.units.mnt}
            quick={[10000, 20000, 50000]}
          />
          <DateField label={t.partners.expiresAt} value={expiresAt} onChange={setExpiresAt} />
          <PickerField
            label={t.partners.customer}
            value={customerId}
            options={customerOptions}
            onChange={setCustomerId}
          />
          <div className="flex items-baseline justify-between gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3">
            <span className="text-sm text-ink-soft">{t.common.total}</span>
            <span className="num text-2xl font-bold text-ink">
              {formatMNT(dMul(faceValue, Math.max(0, Math.round(dToNumber(count)))))}
            </span>
          </div>
          {issueError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {issueError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={voiding !== null}
        onClose={() => setVoiding(null)}
        size="sm"
        title={t.partners.voidVoucher}
        subtitle={voiding?.code}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setVoiding(null)}>
              {t.common.cancel}
            </Button>
            <Button variant="danger" size="md" loading={voidMutation.isPending} onClick={submitVoid}>
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <p className="text-[15px] text-ink">{t.common.deleteConfirm}</p>
          <TextAreaField label={t.common.reason} value={voidReason} onChange={setVoidReason} />
          {voidError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {voidError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default VouchersPage;
