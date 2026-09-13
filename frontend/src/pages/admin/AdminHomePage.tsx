/**
 * Админ панелийн тойм — бүх салбар нэг дэлгэцэнд.
 *
 * Салбар бүрийн карт: ажилтны тоо, нээлттэй ээлж, ээлж нээх журам (миль,
 * зураг) ба «Тохиргоо» товч. Дээр нь системийн ерөнхий тоо: салбар,
 * хэрэглэгч, нээлттэй ээлж, ПОС-ын горим.
 */

import { useNavigate } from "react-router-dom";
import {
  Building2,
  Camera,
  ChevronRight,
  Droplets,
  Gauge,
  LayoutGrid,
  MapPin,
  Plus,
  Power,
  Settings2,
  ShieldCheck,
  UserCog,
  Users,
} from "lucide-react";

import { useBranches } from "../../api/queries/branches";
import { useSettings } from "../../api/queries/system";
import { useUsers } from "../../api/queries/users";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";

function RuleChip({ on, icon, label }: { on: boolean; icon: React.ReactNode; label: string }) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-semibold",
        on ? "border-success/30 bg-success-soft text-success-dark" : "border-line bg-surface-alt text-ink-faint",
      ].join(" ")}
    >
      {icon}
      {label}
    </span>
  );
}

export function AdminHomePage() {
  const navigate = useNavigate();
  const branchesQuery = useBranches();
  const usersQuery = useUsers({ limit: 1 });
  const { data: settings } = useSettings();

  const branches = branchesQuery.data ?? [];
  const activeBranches = branches.filter((b) => b.is_active);
  const openShifts = branches.reduce((sum, b) => sum + b.open_shifts, 0);
  const userTotal = usersQuery.data?.total ?? 0;
  const posOn = settings?.pos_sales_enabled === true || settings?.pos_sales_enabled === "true";

  return (
    <div className="flex flex-col gap-5 sm:gap-6">
      <PageHeader
        title={t.adminPanel.overview}
        subtitle={t.adminPanel.overviewHint}
        icon={<ShieldCheck className="h-6 w-6" />}
        iconTone="danger"
        actions={
          <Button variant="primary" icon={<Plus className="h-5 w-5" />} onClick={() => navigate("/admin/branches")}>
            {t.branches.add}
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatBox
          label={t.adminPanel.statBranches}
          value={activeBranches.length}
          hint={`${branches.length} ${t.adminPanel.statTotalSuffix}`}
          icon={<Building2 className="h-5 w-5" />}
          tone="action"
          onClick={() => navigate("/admin/branches")}
        />
        <StatBox
          label={t.adminPanel.statUsers}
          value={usersQuery.isLoading ? "…" : userTotal}
          icon={<UserCog className="h-5 w-5" />}
          tone="violet"
          onClick={() => navigate("/admin/users")}
        />
        <StatBox
          label={t.adminPanel.statOpenShifts}
          value={openShifts}
          icon={<Gauge className="h-5 w-5" />}
          tone={openShifts > 0 ? "success" : "neutral"}
          onClick={() => navigate("/daily-closings")}
        />
        <StatBox
          label={t.adminPanel.statPosMode}
          value={posOn ? t.adminPanel.posOn : t.adminPanel.posOff}
          hint={posOn ? t.adminPanel.posOnHint : t.adminPanel.posOffHint}
          icon={<Power className="h-5 w-5" />}
          tone={posOn ? "warning" : "brand"}
          onClick={() => navigate("/admin/settings")}
        />
      </div>

      <Card title={t.adminPanel.branchesTitle} subtitle={t.adminPanel.branchesHint}>
        {branchesQuery.isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner size="lg" label={t.common.loading} />
          </div>
        ) : branches.length === 0 ? (
          <EmptyState
            title={t.branches.empty}
            hint={t.adminPanel.noBranchesHint}
            icon={<Building2 className="h-7 w-7" />}
            action={
              <Button variant="primary" icon={<Plus className="h-5 w-5" />} onClick={() => navigate("/admin/branches")}>
                {t.branches.add}
              </Button>
            }
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {branches.map((branch) => (
              <button
                key={branch.id}
                type="button"
                onClick={() => navigate(`/admin/branches/${branch.id}`)}
                className="group flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-action/40 hover:shadow-md active:translate-y-0"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={[
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white shadow-sm",
                      branch.is_active ? "bg-gradient-to-br from-blue-500 to-blue-700" : "bg-slate-400",
                    ].join(" ")}
                  >
                    <Building2 className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-base font-bold text-ink">{branch.name}</span>
                      <span className="num shrink-0 rounded-md bg-surface-sunken px-1.5 py-0.5 text-[11px] font-bold text-ink-soft">
                        {branch.code}
                      </span>
                    </div>
                    {branch.address ? (
                      <div className="mt-0.5 flex items-center gap-1 truncate text-xs text-ink-soft">
                        <MapPin className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{branch.address}</span>
                      </div>
                    ) : null}
                  </div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {branch.is_active ? (
                    <StatusBadge dot tone="success" label={t.common.active} size="sm" />
                  ) : (
                    <StatusBadge dot tone="neutral" label={t.common.inactive} size="sm" />
                  )}
                  {branch.open_shifts > 0 ? (
                    <StatusBadge dot tone="action" label={`${t.branches.openShifts}: ${branch.open_shifts}`} size="sm" />
                  ) : null}
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-ink-soft">
                    <Users className="h-3.5 w-3.5" />
                    {branch.user_count} {t.branches.staff.toLowerCase()}
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <RuleChip on={branch.require_open_mile} icon={<Gauge className="h-3.5 w-3.5" />} label={t.adminPanel.ruleMile} />
                  <RuleChip on={branch.require_open_photo} icon={<Camera className="h-3.5 w-3.5" />} label={t.adminPanel.rulePhoto} />
                </div>

                <span className="mt-auto inline-flex items-center gap-1.5 text-sm font-semibold text-action">
                  <Settings2 className="h-4 w-4" />
                  {t.branches.openSetup}
                </span>
              </button>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { to: "/admin/fuels", icon: Droplets, label: t.nav.fuels, hint: t.adminPanel.quickFuels, tone: "from-sky-500 to-sky-700" },
          { to: "/admin/users", icon: UserCog, label: t.nav.users, hint: t.adminPanel.quickUsers, tone: "from-violet-500 to-violet-700" },
          { to: "/admin/settings", icon: Settings2, label: t.nav.settings, hint: t.adminPanel.quickSettings, tone: "from-amber-400 to-amber-600" },
          { to: "/owner", icon: LayoutGrid, label: t.nav.owner, hint: t.adminPanel.quickOwner, tone: "from-emerald-400 to-emerald-600" },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.to}
              type="button"
              onClick={() => navigate(item.to)}
              className="flex items-center gap-3 rounded-2xl border border-line bg-white p-4 text-left shadow-sm transition-colors hover:bg-surface-alt"
            >
              <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white ${item.tone}`}>
                <Icon className="h-5 w-5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-bold text-ink">{item.label}</span>
                <span className="block truncate text-xs text-ink-soft">{item.hint}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default AdminHomePage;
