import { useState } from "react";
import { useLocation } from "react-router-dom";
import { ChevronDown, type LucideIcon } from "lucide-react";

import { NavItem } from "./NavItem";

export interface NavChild {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export interface NavGroupProps {
  label: string;
  icon: LucideIcon;
  children: readonly NavChild[];
  collapsed?: boolean;
  onNavigate?: () => void;
}

/** Дэд цэстэй нэгж — «Customer → Харилцагч, Нийлүүлэгч» гэх мэт.

Дэд зам идэвхтэй бол автоматаар дэлгээтэй эхэлнэ.  Цэс хураастай үед
дэд цэсүүд нь шууд дүрсээрээ харагдана (нэмэлт товшилт шаардахгүй). */
export function NavGroup({ label, icon: Icon, children, collapsed = false, onNavigate }: NavGroupProps) {
  const location = useLocation();
  const childActive = children.some((child) => location.pathname.startsWith(child.to));
  const [open, setOpen] = useState(childActive);

  if (collapsed) {
    // Хураастай горим: дэд цэсүүд өөрсдөө дүрс болж харагдана.
    return (
      <>
        {children.map((child) => (
          <NavItem
            key={child.to}
            to={child.to}
            label={`${label} · ${child.label}`}
            icon={child.icon}
            end={child.end}
            collapsed
            onNavigate={onNavigate}
          />
        ))}
      </>
    );
  }

  const expanded = open || childActive;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!expanded)}
        aria-expanded={expanded}
        className={[
          "group flex h-12 w-full items-center gap-3 rounded-xl px-3 text-[15px] font-medium transition-colors",
          childActive ? "text-white" : "text-slate-300",
          "hover:bg-brand-800 hover:text-white active:bg-brand-700",
        ].join(" ")}
      >
        <Icon className="h-5 w-5 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-left">{label}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded ? (
        <div className="mt-1 ml-4 space-y-1 border-l border-brand-800 pl-2">
          {children.map((child) => (
            <NavItem
              key={child.to}
              to={child.to}
              label={child.label}
              icon={child.icon}
              end={child.end}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default NavGroup;
