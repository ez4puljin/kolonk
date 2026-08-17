import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Menu, Wifi, WifiOff } from "lucide-react";

import { useCurrentShift } from "../../api/queries/shifts";
import { useSettings } from "../../api/queries/system";
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

function stationName(value: unknown): string {
  return typeof value === "string" && value.trim() !== "" ? value : t.app.name;
}

export function Header({ onLogout, loggingOut = false }: HeaderProps) {
  const navigate = useNavigate();
  const now = useClock();

  const user = useAuthStore((state) => state.user);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const connection = usePumpsStore((state) => state.connection);
  const { enabled: posEnabled } = usePosEnabled();

  const { data: settings } = useSettings();
  const { data: current } = useCurrentShift();

  const shift = current?.shift ?? null;

  return (
    <header className="app-header no-print flex h-16 shrink-0 items-center gap-3 border-b border-brand-800 bg-brand-900 px-3 sm:px-5">
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={t.nav.menu}
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-brand-800 active:bg-brand-700 lg:hidden"
      >
        <Menu className="h-6 w-6" />
      </button>

      <div className="flex min-w-0 items-center gap-3">
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

      <div className="ml-auto flex items-center gap-2 sm:gap-3">
        {/* Түгээгүүрийн холболтын дүрс — ПОС унтраалттай үед socket огт
            нээгддэггүй тул байнга «офлайн» болж төөрөгдүүлэхээс нуугдана. */}
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
          // Гар утсанд хүрэлтийн талбай ≥44px байлгана — badge өөрөө жижиг.
          className="flex min-h-11 shrink-0 items-center"
          aria-label={t.nav.shift}
        >
          {shift ? (
            <StatusBadge
              dot
              tone="success"
              label={`${t.shift.number}${shift.number}`}
              size="sm"
              className="!bg-success/15 !text-success !border-success/40"
            />
          ) : (
            <StatusBadge dot tone="warning" label={t.shift.noOpen} size="sm" className="!bg-warning/15 !text-warning !border-warning/40" />
          )}
        </button>

        <div className="hidden min-w-0 text-right sm:block">
          <div className="truncate text-sm leading-tight font-semibold text-white">
            {user?.full_name ?? "—"}
          </div>
          <div className="truncate text-xs leading-tight text-slate-400">
            {user?.role_name_mn ?? ""}
            {/* Түгээгчийн харьяа салбар — нэвтрэхэд автоматаар сонгогддог. */}
            {user?.branch ? (
              <span className="ml-1 text-emerald-400">· {user.branch.name}</span>
            ) : user?.all_branches ? (
              <span className="ml-1 text-slate-500">· {t.branches.allBranches}</span>
            ) : null}
          </div>
        </div>

        <button
          type="button"
          onClick={onLogout}
          disabled={loggingOut}
          aria-label={t.auth.logout}
          title={t.auth.logout}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-slate-300 transition-colors hover:bg-danger hover:text-white active:bg-danger-dark disabled:opacity-50"
        >
          <LogOut className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}

export default Header;
