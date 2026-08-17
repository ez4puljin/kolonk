import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { t } from "../../i18n/mn";

export type ModalSize = "sm" | "md" | "lg" | "xl" | "full";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  subtitle?: ReactNode;
  size?: ModalSize;
  children: ReactNode;
  footer?: ReactNode;
  /** Хаах товч болон дэвсгэр дарахыг хориглох (заавал шийдвэр гаргах цонх). */
  dismissible?: boolean;
  className?: string;
}

const SIZES: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
  full: "max-w-[96vw] h-[92vh]",
};

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  size = "md",
  children,
  footer,
  dismissible = true,
  className = "",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;

    const handleKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape" && dismissible) {
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose, dismissible]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6">
      <div
        className="absolute inset-0 bg-brand-950/70 backdrop-blur-[2px]"
        onClick={dismissible ? onClose : undefined}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className={[
          "animate-pop relative flex w-full flex-col overflow-hidden bg-surface shadow-2xl",
          "rounded-t-3xl sm:rounded-2xl",
          "max-h-[92vh]",
          SIZES[size],
          className,
        ].join(" ")}
      >
        {(title || dismissible) && (
          <header className="flex shrink-0 items-start gap-4 border-b border-line bg-white px-4 py-3 sm:px-6 sm:py-4">
            <div className="min-w-0 flex-1">
              {title ? <h2 className="truncate text-lg font-bold text-ink sm:text-xl">{title}</h2> : null}
              {subtitle ? <p className="mt-0.5 truncate text-sm text-ink-soft">{subtitle}</p> : null}
            </div>
            {dismissible ? (
              <button
                type="button"
                onClick={onClose}
                aria-label={t.common.close}
                className="-mr-2 flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-ink-soft transition-colors hover:bg-surface-alt active:bg-surface-sunken"
              >
                <X className="h-6 w-6" />
              </button>
            ) : null}
          </header>
        )}

        <div className="scroll-touch min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">{children}</div>

        {footer ? (
          // Утсанд товчнууд өргөнөө тэнцүү хувааж, хуруунд том бай болно.
          <footer className="safe-bottom flex shrink-0 items-center justify-end gap-3 border-t border-line bg-white px-4 py-3 sm:px-6 sm:py-4 [&>button]:flex-1 sm:[&>button]:flex-none">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

export default Modal;
