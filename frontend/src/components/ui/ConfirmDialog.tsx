import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { t } from "../../i18n/mn";
import { Button, type ButtonVariant } from "./Button";
import { Modal } from "./Modal";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Устгах/буцаах гэх мэт эргэшгүй үйлдэлд `danger`. */
  variant?: Extract<ButtonVariant, "primary" | "danger" | "success" | "warning">;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = t.common.confirm,
  cancelLabel = t.common.cancel,
  variant = "primary",
  loading = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={loading ? () => undefined : onCancel}
      size="sm"
      title={title}
      dismissible={!loading}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={variant} size="md" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-4">
        <span
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${
            variant === "danger" ? "bg-danger-soft text-danger-dark" : "bg-warning-soft text-warning-dark"
          }`}
        >
          <AlertTriangle className="h-6 w-6" />
        </span>
        <div className="min-w-0 flex-1 pt-1.5">
          {message ? <div className="text-[15px] text-ink">{message}</div> : null}
          {children}
        </div>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
