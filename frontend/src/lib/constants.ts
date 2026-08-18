import {
  ArrowLeftRight,
  Banknote,
  CreditCard,
  FileText,
  QrCode,
  type LucideIcon,
} from "lucide-react";

import type {
  ApprovalStatus,
  ContractStatus,
  DocStatus,
  EbarimtStatus,
  InvoiceStatus,
  PaymentMethod,
  PumpStatus,
  SaleStatus,
  ShiftStatus,
} from "../api/types";
import { t } from "../i18n/mn";

/** CONTRACTS.md §9-ийн өнгөний палитр. */
export const colors = {
  brand: "#0F172A",
  panel: "#1E293B",
  panelSoft: "#334155",
  surface: "#F8FAFC",
  surfaceAlt: "#F1F5F9",
  line: "#E2E8F0",
  ink: "#0F172A",
  inkSoft: "#475569",
  inkFaint: "#94A3B8",
  success: "#10B981",
  action: "#2563EB",
  warning: "#F59E0B",
  danger: "#EF4444",
  neutral: "#64748B",
} as const;

export type Tone = "success" | "action" | "warning" | "danger" | "violet" | "neutral" | "brand";

export interface TenderMeta {
  value: PaymentMethod;
  label: string;
  icon: LucideIcon;
  color: string;
  /** Бэлэн мөнгө шиг хариулт гардаг эсэх. */
  givesChange: boolean;
  /** Нэмэлт мэдээлэл шаардах эсэх. */
  requires: "none" | "contract" | "ref";
}

export const TENDER_METHODS: readonly TenderMeta[] = [
  {
    value: "cash",
    label: t.tender.cash,
    icon: Banknote,
    color: colors.success,
    givesChange: true,
    requires: "none",
  },
  {
    value: "card",
    label: t.tender.card,
    icon: CreditCard,
    color: colors.action,
    givesChange: false,
    requires: "ref",
  },
  {
    value: "qr",
    label: t.tender.qr,
    icon: QrCode,
    color: "#7C3AED",
    givesChange: false,
    requires: "ref",
  },
  {
    value: "transfer",
    label: t.tender.transfer,
    icon: ArrowLeftRight,
    color: "#0284C7",
    givesChange: false,
    requires: "ref",
  },
  {
    value: "contract",
    label: t.tender.contract,
    icon: FileText,
    color: colors.warning,
    givesChange: false,
    requires: "contract",
  },
] as const;

export const TENDER_BY_METHOD: Record<PaymentMethod, TenderMeta> = TENDER_METHODS.reduce(
  (acc, meta) => {
    acc[meta.value] = meta;
    return acc;
  },
  {} as Record<PaymentMethod, TenderMeta>,
);

export function tenderLabel(method: string): string {
  return TENDER_BY_METHOD[method as PaymentMethod]?.label ?? method;
}

/** Түргэн бэлэн мөнгөний товчнууд (₮). */
export const QUICK_CASH: readonly number[] = [5000, 10000, 20000, 50000, 100000];

export interface StatusMeta {
  label: string;
  tone: Tone;
  color: string;
  /** Цайвар дэвсгэрийн Tailwind анги. */
  chip: string;
}

function meta(label: string, tone: Tone, color: string, chip: string): StatusMeta {
  return { label, tone, color, chip };
}

const CHIP = {
  success: "bg-success-soft text-success-dark border-success/30",
  action: "bg-action-soft text-action-dark border-action/30",
  warning: "bg-warning-soft text-warning-dark border-warning/30",
  danger: "bg-danger-soft text-danger-dark border-danger/30",
  neutral: "bg-surface-sunken text-ink-soft border-line-strong",
  brand: "bg-brand-800 text-ink-invert border-brand-700",
} as const;

export const PUMP_STATUS_META: Record<PumpStatus, StatusMeta> = {
  offline: meta(t.pumps.status.offline, "neutral", colors.neutral, CHIP.neutral),
  idle: meta(t.pumps.status.idle, "action", colors.action, CHIP.action),
  authorized: meta(t.pumps.status.authorized, "warning", colors.warning, CHIP.warning),
  fueling: meta(t.pumps.status.fueling, "success", colors.success, CHIP.success),
  complete: meta(t.pumps.status.complete, "success", colors.success, CHIP.success),
  error: meta(t.pumps.status.error, "danger", colors.danger, CHIP.danger),
};

export const SALE_STATUS_META: Record<SaleStatus, StatusMeta> = {
  draft: meta(t.status.draft, "neutral", colors.neutral, CHIP.neutral),
  completed: meta(t.status.completed, "success", colors.success, CHIP.success),
  refunded: meta(t.status.refunded, "danger", colors.danger, CHIP.danger),
  partial_refund: meta(t.status.partialRefund, "warning", colors.warning, CHIP.warning),
};

export const SHIFT_STATUS_META: Record<ShiftStatus, StatusMeta> = {
  open: meta(t.status.open, "success", colors.success, CHIP.success),
  closed: meta(t.status.closed, "neutral", colors.neutral, CHIP.neutral),
};

export const APPROVAL_STATUS_META: Record<ApprovalStatus, StatusMeta> = {
  pending: meta(t.status.pending, "warning", colors.warning, CHIP.warning),
  approved: meta(t.status.approved, "success", colors.success, CHIP.success),
  rejected: meta(t.status.rejected, "danger", colors.danger, CHIP.danger),
};

export const DOC_STATUS_META: Record<DocStatus, StatusMeta> = {
  draft: meta(t.status.draft, "neutral", colors.neutral, CHIP.neutral),
  posted: meta(t.status.posted, "success", colors.success, CHIP.success),
};

export const INVOICE_STATUS_META: Record<InvoiceStatus, StatusMeta> = {
  open: meta(t.status.unpaid, "warning", colors.warning, CHIP.warning),
  partial: meta(t.status.partial, "action", colors.action, CHIP.action),
  paid: meta(t.status.paid, "success", colors.success, CHIP.success),
};

export const CONTRACT_STATUS_META: Record<ContractStatus, StatusMeta> = {
  active: meta(t.status.active, "success", colors.success, CHIP.success),
  suspended: meta(t.status.suspended, "warning", colors.warning, CHIP.warning),
  closed: meta(t.status.closed, "neutral", colors.neutral, CHIP.neutral),
};



export const EBARIMT_STATUS_META: Record<EbarimtStatus, StatusMeta> = {
  pending: meta(t.status.pending, "warning", colors.warning, CHIP.warning),
  sent: meta(t.status.sent, "success", colors.success, CHIP.success),
  failed: meta(t.status.failed, "danger", colors.danger, CHIP.danger),
};

const UNKNOWN_META = meta(t.status.unknown, "neutral", colors.neutral, CHIP.neutral);

/** Дурын төлвийн кодыг тайлбартай болгоно (сервер шинэ утга нэмсэн ч унахгүй). */
export function statusMeta(
  table: Record<string, StatusMeta>,
  key: string | null | undefined,
  fallbackLabel?: string,
): StatusMeta {
  if (key && table[key]) return table[key];
  return fallbackLabel ? { ...UNKNOWN_META, label: fallbackLabel } : UNKNOWN_META;
}

/** Дүрийн өнгө — нэвтрэх дэлгэцийн плитка. */
export const ROLE_META: Record<string, { label: string; color: string; chip: string }> = {
  owner: { label: "Admin", color: colors.warning, chip: CHIP.warning },
  manager: { label: "Нягтлан", color: colors.action, chip: CHIP.action },
  cashier: { label: "Түгээгч", color: colors.success, chip: CHIP.success },
};

/**
 * Нэвтрэлтийн дараа дүрээр чиглүүлэх зам.
 *
 * Түгээгч ЭЭЛЖИН дээрээ бууна — ээлжээ нээхээс өмнө касс ашиглах
 * боломжгүй бөгөөд ПОС унтраалттай станцад касс огт нээгддэггүй.
 */
export const ROLE_HOME: Record<string, string> = {
  cashier: "/shift",
  manager: "/dashboard",
  owner: "/owner",
};

export function homeForRole(roleCode: string | null | undefined): string {
  if (!roleCode) return "/shift";
  return ROLE_HOME[roleCode] ?? "/shift";
}

/** Урьдчилсан литрийн товчнууд. */
export const PRESET_LITERS: readonly number[] = [10, 20, 30, 50];
/** Урьдчилсан дүнгийн товчнууд (₮). */
export const PRESET_AMOUNTS: readonly number[] = [20000, 30000, 50000, 100000];

export const PAGE_SIZE = 50;
export const POLL_INTERVAL_MS = 15000;
