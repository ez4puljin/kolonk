import type { ReactNode } from "react";

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  /** Дотоод зайг арилгах (хүснэгт бүтнээрээ багтаах үед). */
  flush?: boolean;
  /** Хар бүрхүүл дээр байрлах хувилбар. */
  tone?: "light" | "dark";
  className?: string;
  bodyClassName?: string;
}

export function Card({
  title,
  subtitle,
  actions,
  footer,
  children,
  flush = false,
  tone = "light",
  className = "",
  bodyClassName = "",
}: CardProps) {
  const shell =
    tone === "dark"
      ? "bg-panel border-brand-700 text-ink-invert"
      : "bg-white border-line text-ink";

  const divider = tone === "dark" ? "border-brand-700" : "border-line";
  const subtitleTone = tone === "dark" ? "text-ink-faint" : "text-ink-soft";

  return (
    <section className={`flex flex-col overflow-hidden rounded-xl border ${shell} ${className}`}>
      {(title || actions) && (
        <header className={`flex items-start gap-4 border-b px-5 py-4 ${divider}`}>
          <div className="min-w-0 flex-1">
            {title ? <h3 className="truncate text-base font-bold">{title}</h3> : null}
            {subtitle ? <p className={`mt-0.5 truncate text-sm ${subtitleTone}`}>{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      )}

      <div className={`min-w-0 flex-1 ${flush ? "" : "px-5 py-4"} ${bodyClassName}`}>{children}</div>

      {footer ? <footer className={`border-t px-5 py-3 ${divider}`}>{footer}</footer> : null}
    </section>
  );
}

export default Card;
