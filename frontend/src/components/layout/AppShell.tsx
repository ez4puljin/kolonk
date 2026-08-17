import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Archive,
  BookOpen,
  Boxes,
  Building2,
  PanelLeftClose,
  Calculator,
  CalendarCheck,
  ClipboardCheck,
  Coins,
  Crown,
  Database,
  FileSpreadsheet,
  FileText,
  Fuel,
  Gauge,
  Landmark,
  LayoutDashboard,
  Package,
  Receipt,
  Scale,
  ScrollText,
  Settings,
  ShoppingCart,
  Store,
  TrendingUp,
  Truck,
  UserCog,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { useLogoutMutation } from "../../api/queries/auth";
import { usePosEnabled } from "../../hooks/usePosEnabled";
import { usePumpSocket } from "../../hooks/usePumpSocket";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { useUiStore } from "../../stores/ui";
import { Spinner } from "../ui/Spinner";
import { Toaster } from "../ui/Toast";
import { Header } from "./Header";
import { NavGroup } from "./NavGroup";
import { NavItem } from "./NavItem";

interface NavEntry {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Эдгээрийн аль нэг эрх байхад л харагдана. Хоосон = бүгдэд. */
  permissions: readonly string[];
  end?: boolean;
  /** Дэд цэсүүд — байвал NavGroup болж зурагдана (`to` ашиглагдахгүй). */
  children?: readonly NavEntry[];
}

interface NavSection {
  key: string;
  title: string;
  items: readonly NavEntry[];
}

const NAV: readonly NavSection[] = [
  {
    key: "operations",
    title: t.nav.sections.operations,
    items: [
      { to: "/pos", label: t.nav.pos, icon: Fuel, permissions: ["sales.create"] },
      { to: "/shift", label: t.nav.shift, icon: Gauge, permissions: ["shifts.open", "shifts.close", "shifts.view_all"] },
      { to: "/daily-closings", label: t.nav.dailyClosings, icon: CalendarCheck, permissions: ["shifts.view_all", "shifts.approve"] },
      { to: "/dashboard", label: t.nav.dashboard, icon: LayoutDashboard, permissions: ["sales.view"] },
      { to: "/owner", label: t.nav.owner, icon: Crown, permissions: ["dashboard.owner"] },
      { to: "/sales", label: t.nav.sales, icon: Receipt, permissions: ["sales.view"] },
    ],
  },
  {
    key: "goods",
    title: t.nav.sections.goods,
    items: [
      { to: "/tanks", label: t.nav.tanks, icon: Database, permissions: ["tanks.view"] },
      { to: "/products", label: t.nav.products, icon: Package, permissions: ["products.view"] },
      { to: "/inventory", label: t.nav.inventory, icon: Boxes, permissions: ["inventory.manage"] },
      { to: "/price-changes", label: t.nav.priceChanges, icon: TrendingUp, permissions: ["prices.request", "prices.approve"] },
      { to: "/receipts/fuel", label: t.nav.fuelReceipts, icon: Truck, permissions: ["receipts.create"] },
      { to: "/purchases", label: t.nav.purchases, icon: ShoppingCart, permissions: ["purchases.manage"] },
    ],
  },
  {
    key: "partners",
    title: t.nav.sections.partners,
    items: [
      {
        to: "/customers",
        label: t.nav.customerGroup,
        icon: Users,
        permissions: ["contracts.manage", "suppliers.manage", "payroll.manage"],
        children: [
          { to: "/customers", label: t.nav.customers, icon: Users, permissions: ["contracts.manage"] },
          { to: "/suppliers", label: t.nav.suppliers, icon: Truck, permissions: ["suppliers.manage"] },
          { to: "/employees", label: t.nav.employees, icon: UserCog, permissions: ["payroll.manage"] },
        ],
      },
      { to: "/contracts", label: t.nav.contracts, icon: FileText, permissions: ["contracts.manage"] },
    ],
  },
  {
    key: "finance",
    title: t.nav.sections.finance,
    items: [
      { to: "/expenses", label: t.nav.expenses, icon: Wallet, permissions: ["expenses.manage"] },
      { to: "/bank-accounts", label: t.nav.bankAccounts, icon: Landmark, permissions: ["bank.manage"] },
      { to: "/bank-statements", label: t.nav.bankStatements, icon: FileSpreadsheet, permissions: ["bank.manage"] },
      { to: "/payroll", label: t.nav.payroll, icon: Coins, permissions: ["payroll.manage"] },
      { to: "/approvals", label: t.nav.approvals, icon: ClipboardCheck, permissions: ["prices.approve", "sales.refund.approve"] },
      { to: "/report-center", label: t.nav.reportCenter, icon: FileText, permissions: ["reports.view"] },
      { to: "/reports", label: t.nav.reports, icon: Store, permissions: ["reports.view"], end: true },
      { to: "/reports/inventory", label: t.nav.inventoryReport, icon: Boxes, permissions: ["reports.view"] },
      { to: "/reports/financial", label: t.nav.financialReports, icon: Scale, permissions: ["accounting.view"] },
      { to: "/accounting", label: t.nav.accounting, icon: Calculator, permissions: ["accounting.view"], end: true },
      { to: "/accounting/journal", label: t.nav.journal, icon: BookOpen, permissions: ["accounting.view"] },
      { to: "/accounting/apar", label: t.nav.apar, icon: Wallet, permissions: ["accounting.view"] },
    ],
  },
  {
    key: "admin",
    title: t.nav.sections.admin,
    items: [
      { to: "/branches", label: t.nav.branches, icon: Building2, permissions: ["settings.manage"] },
      { to: "/users", label: t.nav.users, icon: UserCog, permissions: ["users.manage"] },
      { to: "/audit", label: t.nav.audit, icon: ScrollText, permissions: ["audit.view"] },
      { to: "/settings", label: t.nav.settings, icon: Settings, permissions: ["settings.manage"] },
      { to: "/backup", label: t.nav.backup, icon: Archive, permissions: ["backup.manage"] },
    ],
  },
];

/** Гар утасны доод самбарт хамгийн их хэрэглэгддэг 5 очих газар. */
const MOBILE_NAV: readonly NavEntry[] = [
  { to: "/pos", label: t.nav.pos, icon: Fuel, permissions: ["sales.create"] },
  { to: "/shift", label: t.nav.shift, icon: Gauge, permissions: ["shifts.open", "shifts.close", "shifts.view_all"] },
  { to: "/sales", label: t.nav.sales, icon: Receipt, permissions: ["sales.view"] },
  { to: "/tanks", label: t.nav.tanks, icon: Database, permissions: ["tanks.view"] },
  { to: "/dashboard", label: t.nav.dashboard, icon: LayoutDashboard, permissions: ["sales.view"] },
  { to: "/owner", label: t.nav.owner, icon: Crown, permissions: ["dashboard.owner"] },
  { to: "/reports", label: t.nav.reports, icon: Store, permissions: ["reports.view"], end: true },
];

function PageFallback() {
  return (
    <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
      <Spinner size="lg" label={t.common.loading} />
    </div>
  );
}

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { canAny } = usePermission();

  const sidebarOpen = useUiStore((state) => state.sidebarOpen);

  // Цэс хураасан эсэх — сонголтыг санана (десктоп дээр л үйлчилнэ).
  const [navPinnedCollapsed, setNavPinnedCollapsed] = useState<boolean>(
    () => localStorage.getItem("kolonk.navCollapsed") === "1",
  );
  const setNavCollapsed = (value: boolean): void => {
    setNavPinnedCollapsed(value);
    localStorage.setItem("kolonk.navCollapsed", value ? "1" : "0");
  };

  // 1280px-ээс нарийн дэлгэцэнд цэс агуулгын 25%-ийг иддэг тул автоматаар хураана.
  const [narrowDesktop, setNarrowDesktop] = useState<boolean>(() => window.innerWidth < 1280);
  useEffect(() => {
    const sync = (): void => setNarrowDesktop(window.innerWidth < 1280);
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, []);
  const navCollapsed = navPinnedCollapsed || narrowDesktop;
  const setSidebar = useUiStore((state) => state.setSidebar);

  const logoutMutation = useLogoutMutation();

  // ПОС унтраалттай үед Касс/Дэлгүүр цэс нуугдана — түгээгчийн горимд
  // бүх борлуулалт өдрийн хаалтаар бүртгэгддэг.
  const { enabled: posEnabled, loading: posLoading } = usePosEnabled();
  const routeVisible = (to: string): boolean => posEnabled || !to.startsWith("/pos");

  // Түгээгүүрийн шууд телеметр — ЗӨВХӨН ПОС асаалттай үед. Түгээгчийн
  // горимд түгээгүүрийг системээс удирддаггүй тул socket хэрэггүй байсаар
  // 30 секунд тутам дахин холбогдох гэж оролддог байв. Тохиргоо ирэх хүртэл
  // мөн хүлээнэ — дэмий нэг холболт үүсгэхээс сэргийлнэ.
  usePumpSocket(posEnabled && !posLoading);

  // Зам солигдоход гар утасны хажуугийн цэсийг хаана.
  useEffect(() => {
    setSidebar(false);
  }, [location.pathname, setSidebar]);

  const sections = NAV.map((section) => ({
    ...section,
    items: section.items
      .filter((item) => canAny(item.permissions) && routeVisible(item.to))
      .map((item) =>
        item.children
          ? {
              ...item,
              children: item.children.filter(
                (child) => canAny(child.permissions) && routeVisible(child.to),
              ),
            }
          : item,
      )
      .filter((item) => !item.children || item.children.length > 0),
  })).filter((section) => section.items.length > 0);

  const mobileItems = MOBILE_NAV.filter(
    (item) => canAny(item.permissions) && routeVisible(item.to),
  ).slice(0, 5);

  const handleLogout = (): void => {
    logoutMutation.mutate(undefined, {
      onSettled: () => navigate("/login", { replace: true }),
    });
  };

  const navBody = (onNavigate?: () => void, collapsed = false) => (
    <nav className="scroll-touch dark-scroll flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {sections.map((section) => (
        <div key={section.key} className="space-y-1">
          {/* Хураасан үед бүлгийн гарчгийн оронд зураас — босоо зай хэмнэнэ */}
          {collapsed ? (
            <div className="mx-2 border-t border-brand-800 pb-1" />
          ) : (
            <div className="px-3 pb-1 text-[11px] font-bold tracking-widest text-slate-500 uppercase">
              {section.title}
            </div>
          )}
          {section.items.map((item) =>
            item.children ? (
              <NavGroup
                key={item.to}
                label={item.label}
                icon={item.icon}
                collapsed={collapsed}
                onNavigate={onNavigate}
                children={item.children.map((child) => ({
                  to: child.to,
                  label: child.label,
                  icon: child.icon,
                  end: child.end,
                }))}
              />
            ) : (
              <NavItem
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
                end={item.end}
                collapsed={collapsed}
                onNavigate={onNavigate}
              />
            ),
          )}
        </div>
      ))}
    </nav>
  );

  return (
    <div className="dark-scroll flex h-full min-h-0 flex-col bg-brand-900">
      <Header onLogout={handleLogout} loggingOut={logoutMutation.isPending} />

      <div className="flex min-h-0 flex-1">
        {/* Хажуугийн цэс — ≥1024px */}
        <aside
          className={`no-print hidden shrink-0 flex-col border-r border-brand-800 bg-brand-900 transition-[width] duration-200 lg:flex ${
            navCollapsed ? "w-16" : "w-64"
          }`}
        >
          {navBody(undefined, navCollapsed)}

          {/* Цэс хураах — өргөн дэлгэцэнд агуулгад илүү зай өгнө.
              Нарийн дэлгэцэнд хураалт албан журмаар тул товчийг харуулахгүй. */}
          {narrowDesktop ? null : (
            <button
              type="button"
              onClick={() => setNavCollapsed(!navPinnedCollapsed)}
              title={navCollapsed ? t.nav.expand : t.nav.collapse}
              className="flex h-12 items-center gap-3 border-t border-brand-800 px-4 text-[13px] font-medium text-slate-400 transition hover:bg-brand-800 hover:text-white"
            >
              <PanelLeftClose
                className={`h-5 w-5 shrink-0 transition-transform ${navCollapsed ? "rotate-180" : ""}`}
              />
              {navCollapsed ? null : <span>{t.nav.collapse}</span>}
            </button>
          )}

          {navCollapsed ? null : (
            <div className="border-t border-brand-800 px-4 py-3 text-[11px] text-slate-500">
              {t.app.fullName} · {t.app.version}
            </div>
          )}
        </aside>

        {/* Гар утасны цэс */}
        {sidebarOpen ? (
          <div className="no-print fixed inset-0 z-40 flex lg:hidden">
            <div
              className="absolute inset-0 bg-brand-950/70"
              onClick={() => setSidebar(false)}
              aria-hidden="true"
            />
            <aside className="animate-fade-up relative flex w-72 max-w-[85vw] flex-col border-r border-brand-800 bg-brand-900">
              <div className="flex h-16 items-center justify-between border-b border-brand-800 px-4">
                <span className="text-base font-bold text-white">{t.nav.menu}</span>
                <button
                  type="button"
                  onClick={() => setSidebar(false)}
                  aria-label={t.common.close}
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-slate-300 active:bg-brand-700"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              {navBody(() => setSidebar(false))}
            </aside>
          </div>
        ) : null}

        {/* Агуулга */}
        <main className="scroll-touch flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-surface">
          <div className="flex min-h-full flex-1 flex-col px-4 pt-5 pb-28 sm:px-6 lg:pb-6">
            <Suspense fallback={<PageFallback />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>

      {/* Доод самбар — <1024px */}
      {mobileItems.length > 0 ? (
        <nav className="no-print safe-bottom fixed inset-x-0 bottom-0 z-30 flex border-t border-brand-800 bg-brand-900/95 backdrop-blur lg:hidden">
          {mobileItems.map((item) => {
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
                <span
                  className={`flex h-8 w-full max-w-14 items-center justify-center rounded-lg ${active ? "bg-action" : ""}`}
                >
                  <Icon className="h-5 w-5" />
                </span>
                <span className="w-full truncate text-center">{item.label}</span>
              </button>
            );
          })}
        </nav>
      ) : null}

      <Toaster />
    </div>
  );
}

export default AppShell;
