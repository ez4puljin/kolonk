import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

export interface NavItemProps {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Дүрсний тэмдгийн өнгө — цэсний бүлэг бүр өөр өнгөтэй. */
  accent?: string;
  /** `end` — зөвхөн яг тэр зам идэвхтэй гэж үзнэ. */
  end?: boolean;
  badge?: number | null;
  collapsed?: boolean;
  onNavigate?: () => void;
}

export function NavItem({
  to,
  label,
  icon: Icon,
  accent = "bg-slate-500",
  end = false,
  badge,
  collapsed = false,
  onNavigate,
}: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        [
          "group relative flex h-12 items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors",
          collapsed ? "justify-center px-0" : "",
          isActive
            ? "bg-action text-white shadow-sm shadow-action/40"
            : "text-slate-300 hover:bg-brand-800 hover:text-white active:bg-brand-700",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      {({ isActive }) => (
        <>
          {/* Өнгөт дүрсний тэмдэг: цэс урт тул зөвхөн бичгээр ялгахад удаан
              байдаг. Идэвхтэй мөрд тэмдэг тунгалаг цагаан болж, цэнхэр
              дэвсгэртэйгээ зөрчихгүй. */}
          <span
            className={[
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              isActive ? "bg-white/25" : accent,
            ].join(" ")}
          >
            <Icon className="h-[18px] w-[18px] text-white" />
          </span>
          {collapsed ? null : <span className="min-w-0 flex-1 truncate">{label}</span>}
          {badge && badge > 0 ? (
            <span
              className={[
                "num rounded-full bg-danger px-2 py-0.5 text-xs font-bold text-white",
                collapsed ? "absolute top-1 right-1 px-1.5 py-0" : "",
              ].join(" ")}
            >
              {badge > 99 ? "99+" : badge}
            </span>
          ) : null}
        </>
      )}
    </NavLink>
  );
}

export default NavItem;
