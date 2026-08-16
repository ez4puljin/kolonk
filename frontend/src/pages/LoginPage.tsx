import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Fuel, Gauge, Wifi, WifiOff } from "lucide-react";

import { useHealth, useLoginMutation, useLoginTiles, useShiftStatusPreview } from "../api/queries/auth";
import { errorMessage } from "../api/client";
import type { UserTile } from "../api/types";
import { PinPad } from "../components/ui/PinPad";
import { Spinner } from "../components/ui/Spinner";
import { t } from "../i18n/mn";
import { ROLE_META, homeForRole } from "../lib/constants";
import { formatClock, formatDate, formatMNT } from "../lib/format";
import { useAuthStore } from "../stores/auth";

const ROLE_ORDER: readonly string[] = ["cashier", "manager", "owner"];

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function roleMeta(code: string) {
  return ROLE_META[code] ?? { label: code, color: "#64748B", chip: "" };
}

export function LoginPage() {
  const navigate = useNavigate();
  const token = useAuthStore((state) => state.token);
  const roleCode = useAuthStore((state) => state.user?.role_code ?? null);

  const [selected, setSelected] = useState<UserTile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<Date>(() => new Date());

  const { data: tiles, isLoading, isError, refetch } = useLoginTiles();
  const { data: health } = useHealth();
  const { data: shiftPreview } = useShiftStatusPreview(Boolean(token));
  const loginMutation = useLoginMutation();

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Аль хэдийн нэвтэрсэн бол шууд ажлын дэлгэц рүү.
  useEffect(() => {
    if (token) navigate(homeForRole(roleCode), { replace: true });
  }, [token, roleCode, navigate]);

  const grouped = useMemo(() => {
    const map = new Map<string, UserTile[]>();
    for (const tile of tiles ?? []) {
      const list = map.get(tile.role_code) ?? [];
      list.push(tile);
      map.set(tile.role_code, list);
    }
    const known = ROLE_ORDER.filter((code) => map.has(code));
    const rest = [...map.keys()].filter((code) => !ROLE_ORDER.includes(code)).sort();
    return [...known, ...rest].map((code) => ({
      code,
      label: map.get(code)?.[0]?.role_name_mn ?? roleMeta(code).label,
      users: map.get(code) ?? [],
    }));
  }, [tiles]);

  const submitPin = (pin: string): void => {
    if (!selected) return;
    setError(null);
    loginMutation.mutate(
      { user_id: selected.id, pin },
      {
        onSuccess: (data) => navigate(homeForRole(data.user.role_code), { replace: true }),
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  const online = health?.status === "ok";
  const shift = shiftPreview?.shift ?? null;

  return (
    <div className="dark-scroll relative flex min-h-full flex-col overflow-y-auto bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800">
      {/* Дэвсгэрийн гэрэлтэлт */}
      <div
        className="pointer-events-none absolute -top-40 -right-40 h-96 w-96 rounded-full bg-action/20 blur-3xl"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-48 -left-32 h-96 w-96 rounded-full bg-success/10 blur-3xl"
        aria-hidden="true"
      />

      {/* Толгой */}
      <header className="relative flex shrink-0 items-center justify-between gap-4 px-6 py-6 sm:px-10">
        <div className="flex items-center gap-3.5">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-action shadow-lg shadow-action/30">
            <Fuel className="h-6 w-6 text-white" />
          </span>
          <div>
            <div className="text-xl leading-tight font-black tracking-tight text-white">{t.app.name}</div>
            <div className="text-xs leading-tight text-slate-400">{t.app.tagline}</div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {shift ? (
            <span className="hidden items-center gap-2 rounded-full border border-success/40 bg-success/10 px-3.5 py-2 text-sm font-semibold text-success sm:inline-flex">
              <Gauge className="h-4 w-4" />
              {t.shift.number}
              {shift.number} · {formatMNT(shiftPreview?.sales.gross_total ?? "0")}
            </span>
          ) : null}

          <div className="text-right">
            <div className="num text-2xl leading-tight font-bold text-white">{formatClock(now)}</div>
            <div className="num text-xs leading-tight text-slate-400">{formatDate(now)}</div>
          </div>
        </div>
      </header>

      {/* Гол хэсэг */}
      <main className="relative flex flex-1 items-center justify-center px-4 pb-10 sm:px-10">
        {selected ? (
          <section className="flex w-full max-w-md flex-col items-center gap-7 rounded-3xl border border-brand-700 bg-brand-900/70 p-7 shadow-2xl backdrop-blur">
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setError(null);
              }}
              className="flex h-12 w-full items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-400 transition-colors hover:text-white"
            >
              <ChevronLeft className="h-5 w-5" />
              {t.auth.changeUser}
            </button>

            <div className="flex flex-col items-center gap-3">
              <span
                className="flex h-20 w-20 items-center justify-center rounded-2xl text-2xl font-black text-white shadow-lg"
                style={{ backgroundColor: roleMeta(selected.role_code).color }}
              >
                {initials(selected.full_name)}
              </span>
              <div className="text-center">
                <div className="text-xl font-bold text-white">{selected.full_name}</div>
                <div className="text-sm text-slate-400">{selected.role_name_mn}</div>
              </div>
              <div className="text-sm text-slate-400">{t.auth.pinPrompt}</div>
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
        ) : (
          <section className="w-full max-w-4xl">
            <div className="mb-7 text-center">
              <h1 className="text-3xl font-bold text-white">{t.auth.title}</h1>
              <p className="mt-1.5 text-slate-400">{t.auth.subtitle}</p>
            </div>

            {isLoading ? (
              <div className="flex justify-center py-16 text-slate-400">
                <Spinner size="lg" label={t.common.loading} />
              </div>
            ) : isError ? (
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-danger/40 bg-danger/10 px-6 py-10 text-center">
                <div className="text-lg font-semibold text-danger">{t.auth.serverOffline}</div>
                <button
                  type="button"
                  onClick={() => void refetch()}
                  className="h-12 rounded-xl border border-danger/50 px-6 font-semibold text-danger transition-colors hover:bg-danger/15"
                >
                  {t.common.retry}
                </button>
              </div>
            ) : grouped.length === 0 ? (
              <div className="rounded-2xl border border-brand-700 bg-brand-900/60 px-6 py-14 text-center text-slate-400">
                {t.auth.noUsers}
              </div>
            ) : (
              <div className="flex flex-col gap-7">
                {grouped.map((group) => (
                  <div key={group.code}>
                    <div className="mb-3 flex items-center gap-3">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: roleMeta(group.code).color }}
                      />
                      <span className="text-sm font-bold tracking-widest text-slate-400 uppercase">
                        {group.label}
                      </span>
                      <span className="h-px flex-1 bg-brand-700" />
                    </div>

                    <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-4">
                      {group.users.map((user) => {
                        const meta = roleMeta(user.role_code);
                        return (
                          <button
                            key={user.id}
                            type="button"
                            onClick={() => {
                              setSelected(user);
                              setError(null);
                            }}
                            className="group relative flex min-h-36 flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border border-brand-700 bg-brand-800/70 px-3 py-5 transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-600 hover:bg-brand-800 active:translate-y-0 active:bg-brand-700"
                          >
                            <span
                              className="absolute inset-x-0 top-0 h-1.5"
                              style={{ backgroundColor: meta.color }}
                              aria-hidden="true"
                            />
                            <span
                              className="flex h-16 w-16 items-center justify-center rounded-2xl text-xl font-black text-white shadow-md"
                              style={{ backgroundColor: meta.color }}
                            >
                              {initials(user.full_name)}
                            </span>
                            <span className="w-full min-w-0">
                              <span className="block truncate text-base font-bold text-white">
                                {user.full_name}
                              </span>
                              <span className="block truncate text-xs text-slate-400">
                                {user.role_name_mn}
                              </span>
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
        )}
      </main>

      {/* Хөл */}
      <footer className="relative flex shrink-0 items-center justify-between gap-4 border-t border-brand-800 px-6 py-4 text-xs text-slate-500 sm:px-10">
        <span>
          {t.app.fullName} · {t.app.version}
        </span>
        <span className="inline-flex items-center gap-2">
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
      </footer>
    </div>
  );
}

export default LoginPage;
