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
        <header className={`flex items-start gap-4 border-b px-4 py-3 sm:px-5 sm:py-4 ${divider}`}>
          <div className="min-w-0 flex-1">
            {title ? <h3 className="text-base font-bold">{title}</h3> : null}
            {/* Дэд гарчиг тайлбар учир `truncate` байхгүй: утсанд 500px текст
                160px-д шахагдаж утга нь алдагддаг байв. */}
            {subtitle ? <p className={`mt-0.5 text-sm ${subtitleTone}`}>{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      )}

      <div className={`min-w-0 flex-1 ${flush ? "" : "px-4 py-3.5 sm:px-5 sm:py-4"} ${bodyClassName}`}>
        {children}
      </div>

      {footer ? <footer className={`border-t px-4 py-3 sm:px-5 ${divider}`}>{footer}</footer> : null}
    </section>
  );
}

export default Card;
