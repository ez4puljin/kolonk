import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Check, ChevronDown, Globe, Lock, LogOut, Menu, ShieldCheck, Wifi, WifiOff } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useSwitchBranchMutation } from "../../api/queries/auth";
import { useBranches } from "../../api/queries/branches";
import { useCurrentShift } from "../../api/queries/shifts";
import { useSettings } from "../../api/queries/system";
import { usePermission } from "../../hooks/usePermission";
import { usePosEnabled } from "../../hooks/usePosEnabled";
import { t } from "../../i18n/mn";
import { formatClock, formatDate } from "../../lib/format";
import { useAuthStore } from "../../stores/auth";
import { usePumpsStore } from "../../stores/pumps";
import { useUiStore } from "../../stores/ui";
import { StatusBadge } from "../ui/StatusBadge";

export interface HeaderProps {
  onLogout: () => void;
  loggingOut?: boolean;
}

function useClock(): Date {
  const [now, setNow] = useState<Date>(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

/** Утасны өргөн (<640px) — дээд мөрөнд богино шошго хэрэглэнэ. */
function useNarrow(): boolean {
  const query = "(max-width: 639px)";
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = (): void => setNarrow(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

function stationName(value: unknown): string {
  return typeof value === "string" && value.trim() !== "" ? value : t.app.name;
}

/**
 * Ажлын салбарын чип.
 *
 * Түгээгч: салбар нь хатуу — цоожтой ногоон чип, дарагдахгүй.
 * Нягтлан, админ: нэвтрэхдээ сонгосон салбар — дарахад жагсаалт нээгдэж
 * солино (сервер шинэ токен буцаана), «Бүх салбар» сонголттой.
 */
function BranchChip() {
  const user = useAuthStore((state) => state.user);
  const toastError = useUiStore((state) => state.toastError);
  const switchMutation = useSwitchBranchMutation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const switchable = Boolean(user && !user.branch_locked && user.all_branches);
  const { data: branches } = useBranches();

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent): void => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!user) return null;

  const label = user.branch ? user.branch.name : user.all_branches ? t.branches.allBranches : t.branches.noBranch;

  if (!switchable) {
    return (
      <span
        className="hidden h-9 items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 text-xs font-semibold text-emerald-300 sm:inline-flex"
        title={t.header.branchLocked}
      >
        <Building2 className="h-3.5 w-3.5" />
        <span className="max-w-40 truncate">{label}</span>
        <Lock className="h-3 w-3 text-emerald-500/70" />
      </span>
    );
  }

  const choose = (branchId: string | null): void => {
    setOpen(false);
    if ((user.branch?.id ?? null) === branchId) return;
    switchMutation.mutate(
      { branch_id: branchId },
      { onError: (cause) => toastError(errorMessage(cause)) },
    );
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={switchMutation.isPending}
        title={t.header.switchBranch}
        className={[
          "inline-flex h-9 items-center gap-1 rounded-full border px-2.5 text-xs font-semibold transition-colors disabled:opacity-60 sm:gap-1.5 sm:px-3",
          user.branch
            ? "border-blue-400/40 bg-blue-500/15 text-blue-200 hover:bg-blue-500/25"
            : "border-brand-600 bg-brand-800 text-slate-300 hover:bg-brand-700",
        ].join(" ")}
      >
        {user.branch ? <Building2 className="h-3.5 w-3.5" /> : <Globe className="h-3.5 w-3.5" />}
        <span className="max-w-[5.5rem] truncate sm:max-w-44">{label}</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div className="animate-pop absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-brand-700 bg-brand-900 shadow-2xl">
          <div className="px-4 py-2.5 text-[11px] font-bold tracking-widest text-slate-500 uppercase">
            {t.header.switchBranch}
          </div>
          <button
            type="button"
            onClick={() => choose(null)}
            className="flex h-11 w-full items-center gap-3 px-4 text-left text-sm text-slate-200 hover:bg-brand-800"
          >
            <Globe className="h-4 w-4 text-slate-400" />
            <span className="flex-1">{t.branches.allBranches}</span>
            {!user.branch ? <Check className="h-4 w-4 text-success" /> : null}
          </button>
          <div className="mx-3 border-t border-brand-800" />
          {(branches ?? [])
            .filter((b) => b.is_active)
            .map((b) => {
              const active = user.branch?.id === b.id;
              return (
                <button
                  key={b.id}
                  type="button"
                  onClick={() => choose(b.id)}
                  className="flex h-11 w-full items-center gap-3 px-4 text-left text-sm text-slate-200 hover:bg-brand-800"
                >
                  <Building2 className={`h-4 w-4 ${active ? "text-blue-300" : "text-slate-400"}`} />
                  <span className="min-w-0 flex-1 truncate">{b.name}</span>
                  <span className="num text-[11px] text-slate-500">{b.code}</span>
                  {active ? <Check className="h-4 w-4 text-success" /> : null}
                </button>
              );
            })}
        </div>
      ) : null}
    </div>
  );
}

export function Header({ onLogout, loggingOut = false }: HeaderProps) {
  const navigate = useNavigate();
  const now = useClock();

  const user = useAuthStore((state) => state.user);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const connection = usePumpsStore((state) => state.connection);
  const { enabled: posEnabled } = usePosEnabled();
  const { canAny } = usePermission();

  const { data: settings } = useSettings();
  const { data: current, isLoading: shiftLoading } = useCurrentShift();

  const shift = current?.shift ?? null;
  const narrow = useNarrow();
  const isAdmin = canAny(["settings.manage", "users.manage"]);

  return (
    <header className="app-header no-print flex h-16 shrink-0 items-center gap-2 border-b border-brand-800 bg-brand-900 px-2 sm:gap-3 sm:px-5">
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={t.nav.menu}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-brand-800 active:bg-brand-700 sm:h-12 sm:w-12 lg:hidden"
      >
        <Menu className="h-6 w-6" />
      </button>

      <div className="hidden min-w-0 items-center gap-3 sm:flex">
        <span className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-action text-sm font-black text-white sm:flex">
          К
        </span>
        <div className="min-w-0">
          <div className="truncate text-[15px] leading-tight font-bold text-white">
            {stationName(settings?.station_name)}
          </div>
          <div className="num truncate text-xs leading-tight text-slate-400">
            {formatDate(now)} · {formatClock(now)}
          </div>
        </div>
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-3">
        {/* Ажлын салбар — түгээгчид цоожтой, нягтлан/админд солигддог */}
        <BranchChip />

        {posEnabled ? (
          <span
            className="hidden items-center gap-1.5 text-xs font-medium text-slate-400 sm:flex"
            title={connection === "online" ? t.common.online : t.common.offline}
          >
            {connection === "online" ? (
              <Wifi className="h-4 w-4 text-success" />
            ) : (
              <WifiOff className="h-4 w-4 text-warning" />
            )}
          </span>
        ) : null}

        <button
          type="button"
          onClick={() => navigate("/shift")}
          className="flex min-h-11 shrink-0 items-center"
          aria-label={t.nav.shift}
        >
          {shiftLoading ? null : shift ? (
            <StatusBadge
              dot
              tone="success"
              label={`${narrow ? "№" : t.shift.number}${shift.number}`}
              size="sm"
              className="!bg-success/15 !text-success !border-success/40"
            />
          ) : (
            <StatusBadge dot tone="warning" label={narrow ? t.shift.noOpenShort : t.shift.noOpen} size="sm" className="!bg-warning/15 !text-warning !border-warning/40" />
          )}
        </button>

        <div className="hidden min-w-0 text-right md:block">
          <div className="truncate text-sm leading-tight font-semibold text-white">{user?.full_name ?? "—"}</div>
          <div className="truncate text-xs leading-tight text-slate-400">{user?.role_name_mn ?? ""}</div>
        </div>

        {/* Админ панел — зөвхөн удирдах эрхтэй хүнд; ажлын цэсэнд тохиргоо байхгүй. */}
        {isAdmin ? (
          <button
            type="button"
            onClick={() => navigate("/admin")}
            title={t.adminPanel.title}
            aria-label={t.adminPanel.title}
            className="flex h-11 w-11 shrink-0 items-center justify-center gap-2 rounded-xl text-sm font-semibold text-rose-300 sm:h-12 sm:w-auto sm:px-3 transition-colors hover:bg-rose-500/15 active:bg-rose-500/25"
          >
            <ShieldCheck className="h-5 w-5" />
            <span className="hidden xl:inline">{t.adminPanel.title}</span>
          </button>
        ) : null}

        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          aria-label={t.auth.logout}
          title={t.auth.logout}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors sm:h-12 sm:w-12 hover:bg-danger hover:text-white active:bg-danger-dark disabled:opacity-50"
        >
          <LogOut className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}

export default Header;
