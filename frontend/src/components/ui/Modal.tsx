import { useEffect, useRef, type ReactNode } from "react";
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

/* -------------------------------------------------------------------------- *
 * Гар утасны BACK товч цонхыг хаана — аппаас гарахгүй.
 *
 * Android дээр back нь `popstate` өдөөнө. Апп үүнийг боловсруулдаггүй байсан
 * тул хөтөч түүхээрээ буцаж, хаалтын цонх нээлттэй байхад back дарахад
 * Chrome-оос бүрмөсөн гардаг байв.
 *
 * Цонх бүр өөрийн бичлэг түлхэх нь БОЛОХГҮЙ: `history.back()` асинхрон тул
 * автомат шилжилт шиг хурдан хаагаад нээхэд түлхэлт, буцаалт хоёр давхцаж,
 * хоцорсон back нь дөнгөж нээгдсэн цонхыг устгана. Иймд бүх үүрлэсэн цонхонд
 * НЭГ хамгаалах бичлэг ашиглаж, дараалалыг энэ модуль дангаар удирдана —
 * ямар ч үед нэгээс олон back замд явахгүй.
 * -------------------------------------------------------------------------- */
interface GuardEntry {
  close: () => void;
  dismissible: boolean;
}

const modalStack: GuardEntry[] = [];
/** Түүхэнд хамгаалах бичлэг байгаа эсэх. */
let guarded = false;
/** Бидний дуудсан `history.back()` замд явж байгаа эсэх. */
let pendingBack = false;
let listening = false;

function hasGuardState(): boolean {
  const state = window.history.state as { kolonkModal?: boolean } | null;
  return state?.kolonkModal === true;
}

function pushGuard(): void {
  window.history.pushState({ kolonkModal: true }, "");
  guarded = true;
}

function handlePop(): void {
  if (pendingBack) {
    // Өөрсдийн дуудсан back бууж, хамгаалах бичлэг устлаа.
    pendingBack = false;
    guarded = false;
    // Буцаалт замд байх зуур цонх дахин нээгдсэн бол хамгаалалтаа сэргээнэ.
    if (modalStack.length > 0) pushGuard();
    return;
  }
  // Хэрэглэгч back дарж, хамгаалах бичлэгийг иджээ.
  guarded = false;
  const top = modalStack[modalStack.length - 1];
  if (top && top.dismissible) {
    modalStack.pop();
    top.close();
  }
  // Доор нь өөр цонх үлдсэн бол дараагийн back түүнийг хаана — нэг нэгээр.
  if (modalStack.length > 0) pushGuard();
}

function acquireGuard(entry: GuardEntry): void {
  if (!listening) {
    window.addEventListener("popstate", handlePop);
    listening = true;
  }
  modalStack.push(entry);
  if (!guarded && !pendingBack) pushGuard();
}

function releaseGuard(entry: GuardEntry): void {
  const index = modalStack.indexOf(entry);
  if (index === -1) return;
  modalStack.splice(index, 1);
  // Сүүлчийн цонх хаагдсан үед л бичлэгээ буцаана — эс бөгөөс түүхэнд хог
  // үлдэж, дараагийн back юу ч хийхгүй өнгөрнө.
  if (modalStack.length === 0 && guarded && !pendingBack && hasGuardState()) {
    pendingBack = true;
    window.history.back();
  }
}

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
  // `onClose` нь ихэвчлэн inline сум функц — render бүрд шинэ утгатай болно.
  // Хэрэв үүнийг effect-ийн хамааралд оруулбал цонх нээлттэй хэвээр байхад
  // effect дахин дахин ажиллаж, түүхийн бичлэг тасралтгүй нэмэгдэж устана.
  // Иймд хамгийн сүүлийн утгыг ref-д хадгалж, effect-ийг зөвхөн нээлт/хаалтад
  // хамааруулна.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;

    const handleKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape" && dismissible) {
        event.stopPropagation();
        onCloseRef.current();
      }
    };
    window.addEventListener("keydown", handleKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const entry: GuardEntry = { close: () => onCloseRef.current(), dismissible };
    acquireGuard(entry);

    return () => {
      window.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      releaseGuard(entry);
    };
  }, [open, dismissible]);

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
