import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

import { t } from "../../i18n/mn";

export interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  /** Буцах товч харуулах (эсвэл тодорхой зам руу). */
  back?: boolean | string;
  actions?: ReactNode;
  /** Гарчгийн доор байрлах шүүлтүүр/табууд. */
  children?: ReactNode;
  className?: string;
}

export function PageHeader({ title, subtitle, back, actions, children, className = "" }: PageHeaderProps) {
  const navigate = useNavigate();

  const goBack = (): void => {
    if (typeof back === "string") navigate(back);
    else navigate(-1);
  };

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      <div className="flex flex-wrap items-start gap-3">
        {back ? (
          <button
            type="button"
            onClick={goBack}
            aria-label={t.common.back}
            className="-ml-2 flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-ink-soft transition-colors hover:bg-surface-sunken active:bg-line-strong"
          >
            <ChevronLeft className="h-6 w-6" />
          </button>
        ) : null}

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl leading-tight font-bold text-ink">{title}</h1>
          {subtitle ? <div className="mt-1 text-sm text-ink-soft">{subtitle}</div> : null}
        </div>

        {actions ? <div className="no-print flex shrink-0 flex-wrap items-center gap-2.5">{actions}</div> : null}
      </div>

      {children ? <div className="no-print">{children}</div> : null}
    </div>
  );
}

export default PageHeader;
