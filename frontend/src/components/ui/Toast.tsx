import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

import { t } from "../../i18n/mn";
import { useUiStore, type ToastKind } from "../../stores/ui";

const STYLE: Record<ToastKind, string> = {
  success: "border-success/40 bg-success-soft text-success-dark",
  error: "border-danger/40 bg-danger-soft text-danger-dark",
  warning: "border-warning/40 bg-warning-soft text-warning-dark",
  info: "border-action/40 bg-action-soft text-action-dark",
};

const ICON: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

/** ui store-ийн мэдэгдлийн жагсаалтыг зурна. AppShell-д нэг л удаа байрлана. */
export function Toaster() {
  const toasts = useUiStore((state) => state.toasts);
  const dismiss = useUiStore((state) => state.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div
      className="no-print pointer-events-none fixed inset-x-0 top-4 z-[60] flex flex-col items-center gap-2.5 px-4 sm:inset-x-auto sm:right-6 sm:items-end"
      role="region"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = ICON[toast.kind];
        return (
          <div
            key={toast.id}
            className={`animate-fade-up pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-xl border px-4 py-3.5 shadow-lg ${STYLE[toast.kind]}`}
          >
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <span className="min-w-0 flex-1 text-[15px] font-medium break-words">{toast.message}</span>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label={t.common.close}
              className="-mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg opacity-60 transition-opacity hover:opacity-100"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default Toaster;
