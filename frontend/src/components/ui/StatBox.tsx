import type { ReactNode } from "react";

import type { Tone } from "../../lib/constants";

export interface StatBoxProps {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  /** Өөрчлөлт — "+12.4%" гэх мэт. */
  delta?: ReactNode;
  /** @deprecated Дүүргэсэн хайрцагт бүх текст цагаан тул нөлөөгүй. */
  deltaTone?: Tone;
  icon?: ReactNode;
  tone?: Tone;
  size?: "md" | "lg" | "xl";
  onClick?: () => void;
  className?: string;
}

/*
 * Статистик хайрцаг ДҮҮРГЭСЭН градиенттэй.
 *
 * Өмнө нь цагаан дэвсгэр дээр зүүн ирмэгт нимгэн өнгөт зураастай байсан
 * тул хуудас бүхэлдээ саарал харагддаг байв. Тоо нь системийн хамгийн
 * чухал мэдээлэл учир өнгөөр нь тодотгоно — нэг харснаар аль нь орлого,
 * аль нь анхааруулга болох нь ялгарна.
 */
const GRADIENT: Record<Tone, string> = {
  // Цайвар үзүүрийг зориуд гүнзгий авав: emerald-400, amber-400 дээр цагаан
  // текст 2:1-ээс бага харьцаатай болж, шошго уншигдахгүй болдог. Түгээгч
  // эдгээр тоог өдөр бүр уншдаг тул өнгөнөөс уншигдац чухал.
  success: "bg-gradient-to-br from-emerald-500 to-emerald-700 text-white border-transparent",
  action: "bg-gradient-to-br from-blue-500 to-blue-700 text-white border-transparent",
  warning: "bg-gradient-to-br from-amber-500 to-orange-600 text-white border-transparent",
  danger: "bg-gradient-to-br from-red-500 to-red-700 text-white border-transparent",
  violet: "bg-gradient-to-br from-violet-500 to-violet-700 text-white border-transparent",
  neutral: "bg-gradient-to-br from-slate-500 to-slate-700 text-white border-transparent",
  brand: "bg-gradient-to-br from-brand-800 to-brand-950 text-white border-transparent",
};

const VALUE_SIZE: Record<NonNullable<StatBoxProps["size"]>, string> = {
  md: "text-3xl",
  lg: "text-[40px] leading-none",
  xl: "text-[56px] leading-none",
};

export function StatBox({
  label,
  value,
  unit,
  hint,
  delta,
  icon,
  tone = "neutral",
  size = "md",
  onClick,
  className = "",
}: StatBoxProps) {
  const interactive = typeof onClick === "function";

  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-semibold text-white">{label}</span>
        {icon ? <span className="shrink-0 text-white/80">{icon}</span> : null}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className={`num font-bold tracking-tight ${VALUE_SIZE[size]}`}>{value}</span>
        {unit ? <span className="text-lg font-semibold text-white">{unit}</span> : null}
      </div>

      {(delta || hint) && (
        <div className="mt-2 flex items-center gap-2 text-sm text-white/90">
          {delta ? <span className="font-semibold">{delta}</span> : null}
          {hint ? <span>{hint}</span> : null}
        </div>
      )}
    </>
  );

  const shell =
    "relative overflow-hidden rounded-2xl border px-4 py-4 shadow-sm sm:px-6 sm:py-5 " +
    `${GRADIENT[tone]} ${className}`;

  if (interactive) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${shell} touch-target w-full text-left transition-transform hover:-translate-y-0.5 active:translate-y-0`}
      >
        {content}
      </button>
    );
  }

  return <div className={shell}>{content}</div>;
}

export default StatBox;
