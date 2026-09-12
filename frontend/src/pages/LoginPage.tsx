import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  Fuel,
  Gauge,
  KeyRound,
  MapPin,
  ShieldCheck,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";

import { useHealth, useLoginBranches, useLoginMutation, useLoginTiles } from "../api/queries/auth";
import { errorMessage } from "../api/client";
import type { LoginBranch, UserTile } from "../api/types";
import { PinPad } from "../components/ui/PinPad";
import { Spinner } from "../components/ui/Spinner";
import { t } from "../i18n/mn";
import { ROLE_META, homeForRole } from "../lib/constants";
import { formatClock, formatDate } from "../lib/format";
import { useAuthStore } from "../stores/auth";

/**
 * Нэвтрэх дэлгэц — салбар тус бүрээр.
 *
 *   1. Салбар сонгох    — идэвхтэй салбарууд, тус бүрд ээлж нээлттэй эсэх
 *   2. Хэрэглэгч сонгох — тэр салбарын түгээгчид + салбаргүй нягтлан
 *   3. ПИН
 *
 * Админ салбаргүй, доод талын «Админ нэвтрэх»-ээр тусдаа орж админ панел
 * руу очно. Сонгосон салбар серверт очиж токенд хадгалагдана — нягтлан
 * тэр салбарын ээлж, зардал, орлогыг шууд тэнд бүртгэнэ.
 */
type Step = "branch" | "user" | "pin";

const LAST_BRANCH_KEY = "kolonk.lastBranch";
const ROLE_ORDER: readonly string[] = ["cashier", "manager"];

function readLastBranch(): string | null {
  try {
    return localStorage.getItem(LAST_BRANCH_KEY);
  } catch {
    return null;
  }
}

function writeLastBranch(id: string): void {
  try {
    localStorage.setItem(LAST_BRANCH_KEY, id);
  } catch {
    /* хувийн горим — санахгүй ч ажиллана */
  }
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function roleMeta(code: string) {
  return ROLE_META[code] ?? { label: code, color: "#64748B", chip: "" };
}

/** Алхмын заагч — аль шатанд байгааг харуулна. */
function Steps({ current, admin }: { current: Step; admin: boolean }) {
  const items: { key: Step; label: string }[] = admin
    ? [
        { key: "user", label: t.auth.stepAdmin },
        { key: "pin", label: t.auth.pin },
      ]
    : [
        { key: "branch", label: t.auth.stepBranch },
        { key: "user", label: t.auth.stepUser },
        { key: "pin", label: t.auth.pin },
      ];
  const order = items.map((i) => i.key);
  const activeIndex = order.indexOf(current);
  return (
    <ol className="flex items-center gap-2 text-xs font-semibold">
      {items.map((item, index) => {
        const done = index < activeIndex;
        const active = index === activeIndex;
        return (
          <li key={item.key} className="flex items-center gap-2">
            <span
              className={[
                "flex h-6 w-6 items-center justify-center rounded-full border text-[11px]",
                done
                  ? "border-success bg-success text-white"
                  : active
                    ? "border-action bg-action text-white"
                    : "border-brand-600 text-slate-500",
              ].join(" ")}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
            </span>
            <span className={active ? "text-white" : done ? "text-slate-300" : "text-slate-500"}>{item.label}</span>
            {index < items.length - 1 ? <ChevronRight className="h-3.5 w-3.5 text-slate-600" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

export function LoginPage() {
  const navigate = useNavigate();
  const token = useAuthStore((state) => state.token);
  const roleCode = useAuthStore((state) => state.user?.role_code ?? null);

  const [adminMode, setAdminMode] = useState(false);
  const [branch, setBranch] = useState<LoginBranch | null>(null);
  const [selected, setSelected] = useState<UserTile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<Date>(() => new Date());
  const lastBranchId = useMemo(readLastBranch, []);

  const branchesQuery = useLoginBranches();
  const tilesQuery = useLoginTiles();
  const { data: health } = useHealth();
  const loginMutation = useLoginMutation();

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Аль хэдийн нэвтэрсэн бол шууд ажлын дэлгэц рүү.
  useEffect(() => {
    if (token) navigate(homeForRole(roleCode), { replace: true });
  }, [token, roleCode, navigate]);

  const step: Step = selected ? "pin" : adminMode || branch ? "user" : "branch";

  // Сонгосон салбарын хүмүүс: тэр салбарын түгээгчид + салбаргүй нягтлан.
  // Админ энд гарахгүй — тусдаа хаалгаар орно.
  const grouped = useMemo(() => {
    const tiles = tilesQuery.data ?? [];
    const list = adminMode
      ? tiles.filter((u) => u.role_code === "owner")
      : tiles.filter(
          (u) =>
            u.role_code !== "owner" &&
            ((branch && u.branch?.id === branch.id) || (!u.branch_locked && u.all_branches)),
        );
    const map = new Map<string, UserTile[]>();
    for (const tile of list) {
      const arr = map.get(tile.role_code) ?? [];
      arr.push(tile);
      map.set(tile.role_code, arr);
    }
    const known = ROLE_ORDER.filter((code) => map.has(code));
    const rest = [...map.keys()].filter((code) => !ROLE_ORDER.includes(code)).sort();
    return [...known, ...rest].map((code) => ({
      code,
      label: map.get(code)?.[0]?.role_name_mn ?? roleMeta(code).label,
      users: map.get(code) ?? [],
    }));
  }, [tilesQuery.data, branch, adminMode]);

  const pickBranch = (item: LoginBranch): void => {
    setBranch(item);
    setSelected(null);
    setError(null);
    writeLastBranch(item.id);
  };

  const backToBranches = (): void => {
    setBranch(null);
    setSelected(null);
    setAdminMode(false);
    setError(null);
  };

  const submitPin = (pin: string): void => {
    if (!selected) return;
    setError(null);
    loginMutation.mutate(
      { user_id: selected.id, pin, branch_id: adminMode ? null : (branch?.id ?? null) },
      {
        onSuccess: (data) => navigate(homeForRole(data.user.role_code), { replace: true }),
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  const online = health?.status === "ok";
  const branches = branchesQuery.data ?? [];

  // ------------------------------------------------------------------ Хэсгүүд
  const branchGrid = (
    <section className="flex max-h-full w-full flex-col">
      <div className="mb-3 shrink-0 sm:mb-5">
        <h1 className="text-2xl font-bold text-white sm:text-3xl">{t.auth.selectBranch}</h1>
        <p className="mt-1 hidden text-sm text-slate-400 [@media(min-height:600px)]:block sm:text-base">
          {t.auth.selectBranchHint}
        </p>
      </div>

      {branchesQuery.isLoading ? (
        <div className="flex justify-center py-16 text-slate-400">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : branchesQuery.isError ? (
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-danger/40 bg-danger/10 px-6 py-10 text-center">
          <div className="text-lg font-semibold text-danger">{t.auth.serverOffline}</div>
          <button
            type="button"
            onClick={() => void branchesQuery.refetch()}
            className="h-12 rounded-xl border border-danger/50 px-6 font-semibold text-danger transition-colors hover:bg-danger/15"
          >
            {t.common.retry}
          </button>
        </div>
      ) : branches.length === 0 ? (
        <div className="rounded-2xl border border-brand-700 bg-brand-900/60 px-6 py-14 text-center text-slate-400">
          {t.auth.noBranches}
        </div>
      ) : (
        <div className="scroll-touch grid min-h-0 gap-3 overflow-y-auto sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
          {branches.map((item) => {
            const last = item.id === lastBranchId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => pickBranch(item)}
                className={[
                  "group relative flex min-h-24 flex-col gap-2.5 overflow-hidden rounded-2xl border bg-brand-800/70 p-4 text-left transition-all duration-150 hover:bg-brand-800 active:bg-brand-700 sm:min-h-32 sm:p-5 sm:hover:-translate-y-0.5",
                  last ? "border-action/70 shadow-lg shadow-action/20" : "border-brand-700 hover:border-brand-600",
                ].join(" ")}
              >
                <span className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-blue-500 to-emerald-500" aria-hidden="true" />
                <div className="flex items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-action text-white shadow-md shadow-action/30">
                    <Building2 className="h-5 w-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-lg font-bold text-white">{item.name}</span>
                      <span className="num shrink-0 rounded-md bg-brand-700 px-1.5 py-0.5 text-[11px] font-bold text-slate-300">
                        {item.code}
                      </span>
                    </span>
                    {item.address ? (
                      <span className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-400">
                        <MapPin className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{item.address}</span>
                      </span>
                    ) : null}
                  </span>
                  <ChevronRight className="h-5 w-5 shrink-0 text-slate-500 transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-auto flex flex-wrap items-center gap-2 text-xs">
                  {item.open_shift_by ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-success/40 bg-success/10 px-2.5 py-1 font-semibold text-success">
                      <Gauge className="h-3.5 w-3.5" />
                      {t.auth.shiftOpenBy} · {item.open_shift_by}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-600 px-2.5 py-1 font-semibold text-slate-400">
                      <Gauge className="h-3.5 w-3.5" />
                      {t.auth.shiftClosed}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 text-slate-400">
                    <Users className="h-3.5 w-3.5" />
                    {item.staff_count}
                  </span>
                  {last ? <span className="ml-auto font-semibold text-action">{t.auth.lastUsed}</span> : null}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Админ — салбаргүй, тусдаа хаалга */}
      <button
        type="button"
        onClick={() => {
          setAdminMode(true);
          setBranch(null);
          setError(null);
        }}
        className="mt-4 flex h-12 shrink-0 items-center justify-center gap-2 self-center rounded-xl border border-brand-700 px-5 text-sm font-semibold text-slate-400 transition-colors hover:border-rose-500/60 hover:text-rose-300 sm:mt-6"
      >
        <ShieldCheck className="h-4 w-4" />
        {t.auth.adminLogin}
      </button>
    </section>
  );

  const userGrid = (
    <section className="flex max-h-full w-full flex-col">
      <button
        type="button"
        onClick={backToBranches}
        className="mb-2 flex h-11 w-fit items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-400 transition-colors hover:text-white"
      >
        <ChevronLeft className="h-5 w-5" />
        {t.auth.backToBranches}
      </button>
      <div className="mb-3 shrink-0 sm:mb-5">
        <h1 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xl font-bold text-white sm:text-3xl">
          {adminMode ? t.auth.adminLogin : t.auth.selectUser}
          {branch ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-action/40 bg-action/15 px-3 py-1 text-sm font-semibold text-blue-200">
              <Building2 className="h-4 w-4" />
              {branch.name}
            </span>
          ) : null}
          {adminMode ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/40 bg-rose-500/15 px-3 py-1 text-sm font-semibold text-rose-200">
              <ShieldCheck className="h-4 w-4" />
              {t.auth.adminNoBranch}
            </span>
          ) : null}
        </h1>
        <p className="mt-1 hidden text-sm text-slate-400 [@media(min-height:600px)]:block sm:text-base">
          {adminMode ? t.auth.adminLoginHint : t.auth.selectUserHint}
        </p>
      </div>

      {tilesQuery.isLoading ? (
        <div className="flex justify-center py-16 text-slate-400">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : grouped.length === 0 ? (
        <div className="rounded-2xl border border-brand-700 bg-brand-900/60 px-6 py-14 text-center text-slate-400">
          {t.auth.noUsers}
        </div>
      ) : (
        <div className="scroll-touch grid min-h-0 gap-3 overflow-y-auto sm:gap-5 lg:grid-cols-2 lg:gap-6">
          {grouped.map((group) => (
            <div key={group.code} className="min-w-0">
              <div className="mb-2 flex items-center gap-2.5 sm:mb-3 sm:gap-3">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: roleMeta(group.code).color }} />
                <span className="truncate text-sm font-bold tracking-widest text-slate-400 uppercase">{group.label}</span>
                <span className="h-px flex-1 bg-brand-700" />
              </div>
              <div className="flex flex-col gap-2 sm:grid sm:grid-cols-2 sm:gap-3">
                {group.users.map((user) => {
                  const meta = roleMeta(user.role_code);
                  const caption = user.branch_locked && user.branch ? user.branch.name : user.role_name_mn;
                  return (
                    <button
                      key={user.id}
                      type="button"
                      onClick={() => {
                        setSelected(user);
                        setError(null);
                      }}
                      className="group relative flex min-h-14 items-center gap-3 overflow-hidden rounded-2xl border border-brand-700 bg-brand-800/70 py-2.5 pr-3 pl-4 text-left transition-all duration-150 hover:border-brand-600 hover:bg-brand-800 active:bg-brand-700 sm:min-h-28 sm:flex-col sm:justify-center sm:gap-2.5 sm:px-3 sm:py-4 sm:text-center sm:hover:-translate-y-0.5 sm:active:translate-y-0"
                    >
                      <span
                        className="absolute inset-y-0 left-0 w-1.5 sm:inset-x-0 sm:inset-y-auto sm:top-0 sm:h-1.5 sm:w-auto"
                        style={{ backgroundColor: meta.color }}
                        aria-hidden="true"
                      />
                      <span
                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-base font-black text-white shadow-md sm:h-14 sm:w-14 sm:rounded-2xl sm:text-lg"
                        style={{ backgroundColor: meta.color }}
                      >
                        {initials(user.full_name)}
                      </span>
                      <span className="min-w-0 flex-1 sm:w-full sm:flex-none">
                        <span className="block truncate text-[15px] font-bold text-white sm:text-base">{user.full_name}</span>
                        <span className="block truncate text-xs text-slate-400">{caption}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );

  const pinCard = selected ? (
    <section className="scroll-touch flex max-h-full w-full max-w-md flex-col items-center gap-[clamp(0.375rem,2svh,1.75rem)] overflow-y-auto rounded-3xl border border-brand-700 bg-brand-900/70 p-[clamp(0.5rem,2.2svh,1.75rem)] shadow-2xl backdrop-blur">
      <button
        type="button"
        onClick={() => {
          setSelected(null);
          setError(null);
        }}
        className="flex h-11 w-full shrink-0 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-400 transition-colors hover:text-white [@media(max-height:600px)]:h-8"
      >
        <ChevronLeft className="h-5 w-5" />
        {t.auth.changeUser}
      </button>

      <div className="flex w-full shrink-0 flex-row items-center justify-center gap-3 [@media(min-height:640px)]:flex-col [@media(min-height:640px)]:gap-[clamp(0.5rem,1.2svh,0.75rem)]">
        <span
          className="flex h-[clamp(2.75rem,8svh,5rem)] w-[clamp(2.75rem,8svh,5rem)] shrink-0 items-center justify-center rounded-2xl text-xl font-black text-white shadow-lg sm:text-2xl"
          style={{ backgroundColor: roleMeta(selected.role_code).color }}
        >
          {initials(selected.full_name)}
        </span>
        <div className="min-w-0 text-left [@media(min-height:640px)]:text-center">
          <div className="truncate text-lg font-bold text-white sm:text-xl">{selected.full_name}</div>
          <div className="truncate text-sm text-slate-400">
            {selected.role_name_mn}
            {branch ? <span className="text-blue-300"> · {branch.name}</span> : null}
          </div>
        </div>
        <div className="hidden text-sm text-slate-400 [@media(min-height:700px)]:block">{t.auth.pinPrompt}</div>
      </div>

      <PinPad
        onSubmit={submitPin}
        onCancel={() => {
          setSelected(null);
          setError(null);
        }}
        loading={loginMutation.isPending}
        error={error}
      />
    </section>
  ) : null;

  return (
    <div className="dark-scroll relative flex h-full flex-col overflow-hidden bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800 lg:flex-row">
      <div className="pointer-events-none absolute -top-40 -right-40 h-96 w-96 rounded-full bg-action/20 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-48 -left-32 h-96 w-96 rounded-full bg-success/10 blur-3xl" aria-hidden="true" />

      {/* Зүүн: брэнд, цаг, алхмууд — өргөн дэлгэцэд босоо самбар, утсанд толгой мөр */}
      <aside className="relative flex shrink-0 items-center justify-between gap-3 px-4 py-3 sm:px-8 sm:py-5 lg:w-80 lg:flex-col lg:items-start lg:justify-between lg:border-r lg:border-brand-800 lg:px-8 lg:py-8 xl:w-96">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3.5 lg:flex-col lg:items-start lg:gap-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-action shadow-lg shadow-action/30 sm:h-12 sm:w-12 lg:h-16 lg:w-16 lg:rounded-2xl">
            <Fuel className="h-5 w-5 text-white sm:h-6 sm:w-6 lg:h-8 lg:w-8" />
          </span>
          <div className="min-w-0">
            <div className="truncate text-lg leading-tight font-black tracking-tight text-white sm:text-xl lg:text-3xl">
              {t.app.name}
            </div>
            <div className="truncate text-xs leading-tight text-slate-400 lg:mt-1 lg:whitespace-normal lg:text-sm">
              {t.app.tagline}
            </div>
          </div>
        </div>

        <div className="hidden lg:block">
          <Steps current={step} admin={adminMode} />
        </div>

        <div className="flex shrink-0 items-center gap-4 lg:w-full lg:flex-col lg:items-start lg:gap-3">
          <div className="text-right lg:text-left">
            <div className="num text-xl leading-tight font-bold text-white sm:text-2xl lg:text-4xl">{formatClock(now)}</div>
            <div className="num text-xs leading-tight text-slate-400 lg:text-sm">{formatDate(now)}</div>
          </div>
          <span className="hidden items-center gap-2 text-xs lg:inline-flex">
            {online ? (
              <>
                <Wifi className="h-4 w-4 text-success" />
                <span className="text-success">{t.auth.serverOnline}</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4 text-warning" />
                <span className="text-warning">{t.auth.serverOffline}</span>
              </>
            )}
          </span>
        </div>
      </aside>

      <div className="relative flex min-h-0 flex-1 flex-col">
        {/* Утсанд алхмын заагч дээр нь */}
        <div className="shrink-0 px-4 pt-1 lg:hidden">
          <Steps current={step} admin={adminMode} />
        </div>

        <main className="relative flex min-h-0 flex-1 items-start justify-center px-4 pt-3 pb-4 sm:px-8 sm:pt-6 sm:pb-8 lg:items-center lg:px-12">
          <div className="flex max-h-full w-full max-w-6xl justify-center">
            {step === "pin" ? pinCard : step === "user" ? userGrid : branchGrid}
          </div>
        </main>

        <footer className="relative flex shrink-0 items-center justify-between gap-3 border-t border-brand-800 px-4 py-2.5 text-[11px] text-slate-500 sm:px-8 sm:py-3 sm:text-xs">
          <span className="min-w-0 truncate">
            {t.app.fullName} · {t.app.version}
          </span>
          <span className="inline-flex shrink-0 items-center gap-2 lg:hidden">
            {online ? (
              <>
                <Wifi className="h-4 w-4 text-success" />
                <span className="text-success">{t.auth.serverOnline}</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4 text-warning" />
                <span className="text-warning">{t.auth.serverOffline}</span>
              </>
            )}
          </span>
          <span className="hidden items-center gap-1.5 text-slate-600 lg:inline-flex">
            <KeyRound className="h-3.5 w-3.5" />
            {t.auth.pinHintFooter}
          </span>
        </footer>
      </div>
    </div>
  );
}

export default LoginPage;
