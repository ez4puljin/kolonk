import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Archive,
  ArrowLeftRight,
  Building2,
  Droplets,
  LayoutGrid,
  LogOut,
  Menu,
  ScrollText,
  Settings,
  ShieldCheck,
  UserCog,
  X,
  type LucideIcon,
} from "lucide-react";

import { useLogoutMutation } from "../../api/queries/auth";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { formatClock, formatDate } from "../../lib/format";
import { useAuthStore } from "../../stores/auth";
import { Spinner } from "../ui/Spinner";
import { Toaster } from "../ui/Toast";
import { NavItem } from "./NavItem";

/**
 * Админ панел — ажлын системээс ТУСДАА бүрхүүл.
 *
 * Салбар, хэрэглэгч, тохиргоо, аудит, нөөцлөлт энд байрлана; ажлын
 * системийн цэсэнд «Удирдлага» хэсэг байхгүй. Ингэснээр түгээгч, нягтлан
 * өдөр тутмын цэсэндээ тохиргооны зүйл харахгүй, админ нэг газраас бүх
 * салбараа удирдана. Өнгө: ягаан (rose) — ажлын системийн цэнхэрээс ялгарна.
 */
interface AdminNavEntry {
  to: string;
  label: string;
  icon: LucideIcon;
  permissions: readonly string[];
  end?: boolean;
}

const ADMIN_NAV: readonly AdminNavEntry[] = [
  { to: "/admin", label: t.adminPanel.overview, icon: LayoutGrid, permissions: [], end: true },
  { to: "/admin/branches", label: t.nav.branches, icon: Building2, permissions: ["settings.manage"] },
  { to: "/admin/fuels", label: t.nav.fuels, icon: Droplets, permissions: ["settings.manage"] },
  { to: "/admin/users", label: t.nav.users, icon: UserCog, permissions: ["users.manage"] },
  { to: "/admin/settings", label: t.nav.settings, icon: Settings, permissions: ["settings.manage"] },
  { to: "/admin/audit", label: t.nav.audit, icon: ScrollText, permissions: ["audit.view"] },
  { to: "/admin/backup", label: t.nav.backup, icon: Archive, permissions: ["backup.manage"] },
];

function useClock(): Date {
  const [now, setNow] = useState<Date>(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

function PageFallback() {
  return (
    <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
      <Spinner size="lg" label={t.common.loading} />
    </div>
  );
}

export function AdminShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const now = useClock();
  const { canAny } = usePermission();
  const user = useAuthStore((state) => state.user);
  const logoutMutation = useLogoutMutation();
  const [menuOpen, setMenuOpen] = useState(false);

  // Зам солигдоход гар утасны хажуугийн цэсийг хаана.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const items = ADMIN_NAV.filter((item) => canAny(item.permissions));

  const handleLogout = (): void => {
    logoutMutation.mutate(undefined, {
      onSettled: () => navigate("/login", { replace: true }),
    });
  };

  const navBody = (onNavigate?: () => void) => (
    <nav className="scroll-touch dark-scroll flex-1 space-y-1 overflow-y-auto px-3 py-4">
      <div className="px-3 pb-2 text-[11px] font-bold tracking-widest text-rose-300/70 uppercase">
        {t.adminPanel.title}
      </div>
      {items.map((item) => (
        <NavItem
          key={item.to}
          to={item.to}
          label={item.label}
          icon={item.icon}
          accent="bg-rose-500"
          end={item.end}
          onNavigate={onNavigate}
        />
      ))}

      <div className="mx-3 my-4 border-t border-brand-800" />

      {/* Ажлын систем рүү — админ салбарын ажлыг хянахдаа энгийн цэс рүү шилжинэ. */}
      <button
        type="button"
        onClick={() => {
          onNavigate?.();
          navigate("/owner");
        }}
        className="group flex h-12 w-full items-center gap-3 rounded-xl px-3 text-[15px] font-medium text-slate-300 transition-colors hover:bg-brand-800 hover:text-white active:bg-brand-700"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-500">
          <ArrowLeftRight className="h-[18px] w-[18px] text-white" />
        </span>
        <span className="min-w-0 flex-1 truncate text-left">{t.adminPanel.toWorkspace}</span>
      </button>
    </nav>
  );

  return (
    <div className="dark-scroll flex h-full min-h-0 flex-col bg-brand-900">
      {/* Толгой — ягаан зурвасаар ажлын системээс ялгарна */}
      <header className="no-print flex h-16 shrink-0 items-center gap-3 border-b border-rose-500/30 bg-brand-900 px-3 sm:px-5">
        <span className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-rose-500 via-rose-400 to-amber-400" aria-hidden="true" />
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          aria-label={t.nav.menu}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-brand-800 active:bg-brand-700 lg:hidden"
        >
          <Menu className="h-6 w-6" />
        </button>

        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-rose-500 to-rose-700 text-white shadow-sm shadow-rose-500/30">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="truncate text-[15px] leading-tight font-bold text-white">{t.adminPanel.title}</div>
            <div className="num truncate text-xs leading-tight text-slate-400">
              {t.app.name} · {formatDate(now)} · {formatClock(now)}
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <div className="hidden min-w-0 text-right sm:block">
            <div className="truncate text-sm leading-tight font-semibold text-white">{user?.full_name ?? "—"}</div>
            <div className="truncate text-xs leading-tight text-rose-300">{user?.role_name_mn ?? ""}</div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={logoutMutation.isPending}
            aria-label={t.auth.logout}
            title={t.auth.logout}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-danger hover:text-white active:bg-danger-dark disabled:opacity-50"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="no-print hidden w-64 shrink-0 flex-col border-r border-brand-800 bg-brand-900 lg:flex">
          {navBody()}
          <div className="border-t border-brand-800 px-4 py-3 text-[11px] text-slate-500">
            {t.app.fullName} · {t.app.version}
          </div>
        </aside>

        {menuOpen ? (
          <div className="no-print fixed inset-0 z-40 flex lg:hidden">
            <div className="absolute inset-0 bg-brand-950/70" onClick={() => setMenuOpen(false)} aria-hidden="true" />
            <aside className="animate-fade-up relative flex w-72 max-w-[85vw] flex-col border-r border-brand-800 bg-brand-900">
              <div className="flex h-16 items-center justify-between border-b border-brand-800 px-4">
                <span className="text-base font-bold text-white">{t.adminPanel.title}</span>
                <button
                  type="button"
                  onClick={() => setMenuOpen(false)}
                  aria-label={t.common.close}
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-slate-300 active:bg-brand-700"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              {navBody(() => setMenuOpen(false))}
            </aside>
          </div>
        ) : null}

        <main className="scroll-touch flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-surface">
          <div className="mx-auto flex min-h-full w-full max-w-[1400px] shrink-0 flex-col px-4 pt-5 pb-28 sm:px-6 lg:pb-6">
            <Suspense fallback={<PageFallback />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>

      {/* Доод самбар — <1024px */}
      <nav className="no-print safe-bottom fixed inset-x-0 bottom-0 z-30 flex border-t border-brand-800 bg-brand-900/95 backdrop-blur lg:hidden">
        {items.slice(0, 5).map((item) => {
          const Icon = item.icon;
          const active = item.end
            ? location.pathname === item.to
            : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
          return (
            <button
              key={item.to}
              type="button"
              onClick={() => navigate(item.to)}
              className={[
                "flex min-h-16 flex-1 flex-col items-center justify-center gap-1 px-1 py-2 text-[11px] font-semibold transition-colors",
                active ? "text-white" : "text-slate-400 active:text-white",
              ].join(" ")}
            >
              <span className={`flex h-8 w-full max-w-14 items-center justify-center rounded-lg ${active ? "bg-rose-500" : ""}`}>
                <Icon className="h-5 w-5" />
              </span>
              <span className="w-full truncate text-center">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <Toaster />
    </div>
  );
}

export default AdminShell;
