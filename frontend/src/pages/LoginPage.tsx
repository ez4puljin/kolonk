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
    // Хуудас өөрөө хэзээ ч гүйхгүй (overflow-hidden) — хэрэглэгч олон үед
    // зөвхөн плиткануудын хэсэг дотроо гүйнэ.
    <div className="dark-scroll relative flex h-full flex-col overflow-hidden bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800">
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
      <header className="relative flex shrink-0 items-center justify-between gap-3 px-4 py-3 sm:px-10 sm:py-6">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-action shadow-lg shadow-action/30 sm:h-12 sm:w-12">
            <Fuel className="h-5 w-5 text-white sm:h-6 sm:w-6" />
          </span>
          <div className="min-w-0">
            <div className="truncate text-lg leading-tight font-black tracking-tight text-white sm:text-xl">
              {t.app.name}
            </div>
            <div className="truncate text-xs leading-tight text-slate-400">{t.app.tagline}</div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-4">
          {shift ? (
            <span className="hidden items-center gap-2 rounded-full border border-success/40 bg-success/10 px-3.5 py-2 text-sm font-semibold text-success sm:inline-flex">
              <Gauge className="h-4 w-4" />
              {t.shift.number}
              {shift.number} · {formatMNT(shiftPreview?.sales.gross_total ?? "0")}
            </span>
          ) : null}

          <div className="text-right">
            <div className="num text-xl leading-tight font-bold text-white sm:text-2xl">{formatClock(now)}</div>
            <div className="num text-xs leading-tight text-slate-400">{formatDate(now)}</div>
          </div>
        </div>
      </header>

      {/* Гол хэсэг */}
      <main className="relative flex min-h-0 flex-1 items-center justify-center px-4 pb-4 sm:px-10 sm:pb-10">
        {selected ? (
          // Хэмжээсүүд дэлгэцийн өндрөөс (svh) хамаарч агшиж тэлдэг тул ПИН-ий
          // карт ямар ч утсанд scroll-гүй бүтэн багтана. overflow-y-auto нь
          // зөвхөн хэвтээ эргүүлсэн утасны аюулгүйн нөөц.
          <section className="scroll-touch flex max-h-full w-full max-w-md flex-col items-center gap-[clamp(0.625rem,2svh,1.75rem)] overflow-y-auto rounded-3xl border border-brand-700 bg-brand-900/70 p-[clamp(0.875rem,2.2svh,1.75rem)] shadow-2xl backdrop-blur">
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setError(null);
              }}
              className="flex h-9 w-full shrink-0 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-slate-400 transition-colors hover:text-white"
            >
              <ChevronLeft className="h-5 w-5" />
              {t.auth.changeUser}
            </button>

            <div className="flex shrink-0 flex-col items-center gap-[clamp(0.5rem,1.2svh,0.75rem)]">
              <span
                className="flex h-[clamp(3.25rem,8svh,5rem)] w-[clamp(3.25rem,8svh,5rem)] items-center justify-center rounded-2xl text-xl font-black text-white shadow-lg sm:text-2xl"
                style={{ backgroundColor: roleMeta(selected.role_code).color }}
              >
                {initials(selected.full_name)}
              </span>
              <div className="text-center">
                <div className="text-lg font-bold text-white sm:text-xl">{selected.full_name}</div>
                <div className="text-sm text-slate-400">{selected.role_name_mn}</div>
              </div>
              {/* Намхан дэлгэцэд нуугдана — "Нэвтрэх" гарчиг хангалттай. */}
              <div className="hidden text-sm text-slate-400 [@media(min-height:700px)]:block">
                {t.auth.pinPrompt}
              </div>
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
          <section className="flex max-h-full w-full max-w-6xl flex-col">
            <div className="mb-3 shrink-0 text-center sm:mb-6">
              <h1 className="text-2xl font-bold text-white sm:text-3xl">{t.auth.title}</h1>
              <p className="mt-1.5 text-sm text-slate-400 sm:text-base">{t.auth.subtitle}</p>
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
              /*
               * Дүрийн бүлгүүд ӨРГӨН дэлгэцэд ЗЭРЭГЦЭЭ багана болно.
               *
               * Өмнө нь бүлэг бүр бүтэн мөр эзэлж, 1920px дээр ердөө 2 багана
               * ашиглаад босоо тэнхлэгээ дуусгадаг байв — Chrome-ийн хаягийн
               * мөр багассан өндрийг тооцвол хамгийн доод бүлэг халиж, scroll
               * заавал шаардагддаг байлаа. Зэрэгцүүлснээр 4 хэрэглэгч нэг
               * эгнээнд багтаж, олон хэрэглэгчтэй үед ч босоо өсөлт удаан.
               */
              <div className="scroll-touch grid min-h-0 gap-3 overflow-y-auto sm:gap-5 lg:grid-cols-3 lg:gap-6">
                {grouped.map((group) => (
                  <div key={group.code} className="min-w-0">
                    <div className="mb-2 flex items-center gap-2.5 sm:mb-3 sm:gap-3">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: roleMeta(group.code).color }}
                      />
                      <span className="truncate text-sm font-bold tracking-widest text-slate-400 uppercase">
                        {group.label}
                      </span>
                      <span className="h-px flex-1 bg-brand-700" />
                    </div>

                    {/* Утсанд: бүтэн өргөнтэй жагсаалтын мөр — нэг дэлгэцэд
                        илүү олон хүн багтаж, товших талбай өргөн байна.
                        Дэлгэцээс дээш: хайрцаг хэлбэрийн плитка. */}
                    <div className="flex flex-col gap-2 sm:grid sm:grid-cols-2 sm:gap-3">
                      {group.users.map((user) => {
                        const meta = roleMeta(user.role_code);
                        // Хоёрдогч мөр: салбартай бол салбараа (нэг ангилалд
                        // олон салбарын түгээгч байхад ялгагдана), эс бөгөөс дүр.
                        const caption = user.branch?.name ?? user.role_name_mn;
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
                            {/* Дүрийн өнгө: утсанд зүүн ирмэг, дэлгэцэд дээд зурвас */}
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
                              <span className="block truncate text-[15px] font-bold text-white sm:text-base">
                                {user.full_name}
                              </span>
                              <span className="block truncate text-xs text-slate-400">
                                {caption}
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
      <footer className="relative flex shrink-0 items-center justify-between gap-3 border-t border-brand-800 px-4 py-2.5 text-[11px] text-slate-500 sm:px-10 sm:py-4 sm:text-xs">
        <span className="min-w-0 truncate">
          {t.app.fullName} · {t.app.version}
        </span>
        <span className="inline-flex shrink-0 items-center gap-2">
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
