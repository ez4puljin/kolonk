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
  /** Гарчгийн зүүн талд гарах өнгөт дүрс. */
  icon?: ReactNode;
  /** Дүрсний тэмдгийн градиент (Tailwind анги). */
  iconTone?: "action" | "success" | "warning" | "danger" | "violet";
  /** Гарчгийн доор байрлах шүүлтүүр/табууд. */
  children?: ReactNode;
  className?: string;
}

const ICON_TONE = {
  action: "from-blue-500 to-blue-700",
  success: "from-emerald-400 to-emerald-600",
  warning: "from-amber-400 to-amber-600",
  danger: "from-red-400 to-red-600",
  violet: "from-violet-400 to-violet-600",
} as const;

export function PageHeader({
  title,
  subtitle,
  back,
  actions,
  icon,
  iconTone = "action",
  children,
  className = "",
}: PageHeaderProps) {
  const navigate = useNavigate();

  const goBack = (): void => {
    if (typeof back === "string") navigate(back);
    else navigate(-1);
  };

  return (
    <div className={`flex flex-col gap-3 sm:gap-4 ${className}`}>
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

        {/* Өнгөт дүрс — хуудас бүр өөрийн таних тэмдэгтэй болно. */}
        {icon ? (
          <span
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm sm:h-12 sm:w-12 ${ICON_TONE[iconTone]}`}
          >
            {icon}
          </span>
        ) : null}

        {/* basis-72: товчнууд олон бол гарчгийг «Түгээ…» болтол шахахын оронд
            товчнууд доод мөрөнд шилжинэ. */}
        <div className="min-w-0 flex-1 basis-72">
          <h1 className="truncate text-xl leading-tight font-bold text-ink sm:text-2xl">{title}</h1>
          {subtitle ? <div className="mt-1 text-[13px] text-ink-soft sm:text-sm">{subtitle}</div> : null}
        </div>

        {/* Утсанд гарчгийн доор бүтэн өргөнөөр — товчнууд дэлгэцээс халихгүй. */}
        {/* Утсанд 2 баганатай тор: товч бүр ижил өргөн, бичиг «…» болж тасрахгүй
            2 мөрөнд хуваагдана; сондгой сүүлийн товч бүтэн мөр эзэлнэ.
            Өмнө нь товч бүр өөр өөр өргөнтэй, нэг нэгээрээ доош жагсдаг байв. */}
        {actions ? (
          <div
            className={[
              "no-print grid w-full grid-cols-2 items-stretch gap-2",
              "[&>*]:w-full [&>*]:min-w-0 [&>*:last-child:nth-child(odd)]:col-span-2",
              "[&>button]:h-auto [&>button]:min-h-12 [&>button]:px-3 [&>button]:py-2 [&>button_span.truncate]:whitespace-normal [&>button_span.truncate]:leading-tight",
              "sm:flex sm:w-auto sm:shrink-0 sm:flex-wrap sm:items-center sm:gap-2.5",
              "sm:[&>*]:w-auto sm:[&>button]:h-12 sm:[&>button]:px-5 sm:[&>button_span.truncate]:whitespace-nowrap",
            ].join(" ")}
          >
            {actions}
          </div>
        ) : null}
      </div>

      {children ? <div className="no-print">{children}</div> : null}
    </div>
  );
}

export default PageHeader;
