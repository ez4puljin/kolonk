import { Suspense, lazy, type ComponentType, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { PowerOff, ShieldAlert } from "lucide-react";

import { AppShell } from "./components/layout/AppShell";
import { Button } from "./components/ui/Button";
import { Spinner } from "./components/ui/Spinner";
import { usePermission } from "./hooks/usePermission";
import { usePosEnabled } from "./hooks/usePosEnabled";
import { t } from "./i18n/mn";
import { homeForRole } from "./lib/constants";
import { useAuthStore } from "./stores/auth";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";

/**
 * Хуудсуудыг залгах.
 *
 * Дэлгэц бүрийг өөр багууд (WP10-WP14) нэмнэ. Vite-ийн `import.meta.glob`
 * тухайн үед байгаа файлуудыг л буцаадаг тул хараахан бичигдээгүй хуудсыг
 * `_Placeholder`-оор орлуулна — бодит файл нэмэгдмэгц автоматаар солигдоно.
 * Импорт унасан тохиолдолд ч мөн адил `_Placeholder` рүү шилжинэ.
 */
const pageModules = import.meta.glob([
  "./pages/**/*.tsx",
  "!./pages/LoginPage.tsx",
  "!./pages/NotFoundPage.tsx",
]);

type PageModule = { default: ComponentType };
type PageLoader = () => Promise<unknown>;

/**
 * Маршрутын нэр → файлын боломжит нэрс.
 *
 * Дэлгэцүүдийг өөр өөр баг бичсэн тул файлын нэр маршрутын нэртэй үргэлж
 * давхцахгүй. Эхэлж маршрутын нэрээр, дараа нь эдгээр хувилбаруудаар хайна.
 */
const PAGE_ALIASES: Record<string, string[]> = {
  PosPage: ["FuelPosPage"],
  PosStorePage: ["StorePosPage"],
  PosPaymentPage: ["PaymentPage"],
  PosBulkPage: ["BulkPosPage"],
  DashboardPage: ["CashierDashboard", "CashierDashboardPage"],
  OwnerDashboardPage: ["OwnerDashboard"],
  FuelReceiptNewPage: ["FuelReceiptFormPage"],
  PurchaseNewPage: ["PurchaseFormPage"],
  SalesPage: ["SalesHistoryPage"],
  RefundPage: ["RefundRequestPage"],
  FinancialReportsPage: ["FinancialStatementsPage"],
  AccountingPage: ["CoaPage", "ChartOfAccountsPage"],
  AuditPage: ["AuditLogPage"],
};

/** `PosPage` → `./pages/PosPage.tsx`, дэд хавтас, эсвэл alias нэр. */
function findLoader(name: string): PageLoader | undefined {
  for (const candidate of [name, ...(PAGE_ALIASES[name] ?? [])]) {
    const exact = pageModules[`./pages/${candidate}.tsx`];
    if (exact) return exact;
    const suffix = `/${candidate}.tsx`;
    const key = Object.keys(pageModules).find((path) => path.endsWith(suffix));
    if (key) return pageModules[key];
  }
  return undefined;
}

async function placeholder(): Promise<PageModule> {
  const mod = await import("./pages/_Placeholder");
  return { default: mod.default };
}

function lazyPage(name: string) {
  return lazy(async (): Promise<PageModule> => {
    const loader = findLoader(name);
    if (!loader) return placeholder();
    return loader()
      .then((loaded): PageModule | Promise<PageModule> => {
        const mod = loaded as Partial<PageModule>;
        return mod.default ? { default: mod.default } : placeholder();
      })
      .catch(placeholder);
  });
}

// --- Дэлгэцүүд ------------------------------------------------------------
const PosPage = lazyPage("PosPage");
const PosStorePage = lazyPage("PosStorePage");
const PosPaymentPage = lazyPage("PosPaymentPage");
const PosBulkPage = lazyPage("PosBulkPage");
const ShiftPage = lazyPage("ShiftPage");
const ShiftReportPage = lazyPage("ShiftReportPage");
const DailyClosingsPage = lazyPage("DailyClosingsPage");
const DashboardPage = lazyPage("DashboardPage");
const OwnerDashboardPage = lazyPage("OwnerDashboardPage");
const TanksPage = lazyPage("TanksPage");
const TankDetailPage = lazyPage("TankDetailPage");
const PurchasesPage = lazyPage("PurchasesPage");
const ExpensesPage = lazyPage("ExpensesPage");
const BankAccountsPage = lazyPage("BankAccountsPage");
const BankStatementsPage = lazyPage("BankStatementsPage");
const InventoryReportPage = lazyPage("InventoryReportPage");
const ReportCenterPage = lazyPage("ReportCenterPage");
const PayrollPage = lazyPage("PayrollPage");
const EmployeesPage = lazyPage("EmployeesPage");
const PurchaseNewPage = lazyPage("PurchaseNewPage");
const ReceiveNewPage = lazyPage("ReceiveNewPage");
const SuppliersPage = lazyPage("SuppliersPage");
const ProductsPage = lazyPage("ProductsPage");
const InventoryPage = lazyPage("InventoryPage");
const PriceChangesPage = lazyPage("PriceChangesPage");
const CustomersPage = lazyPage("CustomersPage");
const ContractsPage = lazyPage("ContractsPage");
const SalesPage = lazyPage("SalesPage");
const SaleDetailPage = lazyPage("SaleDetailPage");
const RefundPage = lazyPage("RefundPage");
const ApprovalsPage = lazyPage("ApprovalsPage");
const ReportsPage = lazyPage("ReportsPage");
const FinancialReportsPage = lazyPage("FinancialReportsPage");
const AccountingPage = lazyPage("AccountingPage");
const JournalPage = lazyPage("JournalPage");
const ApArPage = lazyPage("ApArPage");
const UsersPage = lazyPage("UsersPage");
const BranchesPage = lazyPage("BranchesPage");
const BranchSetupPage = lazyPage("BranchSetupPage");
const AuditPage = lazyPage("AuditPage");
const SettingsPage = lazyPage("SettingsPage");
const BackupPage = lazyPage("BackupPage");

// --- Хамгаалалт -----------------------------------------------------------

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore((state) => state.token);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

function Forbidden() {
  return (
    <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center gap-5 text-center">
      <span className="flex h-20 w-20 items-center justify-center rounded-full bg-danger-soft text-danger-dark">
        <ShieldAlert className="h-10 w-10" />
      </span>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-ink">{t.auth.forbidden}</h1>
        <p className="max-w-md text-ink-soft">{t.auth.forbiddenHint}</p>
      </div>
      <Button variant="secondary" size="lg" onClick={() => window.history.back()}>
        {t.common.back}
      </Button>
    </div>
  );
}

function RequirePermission({ code, children }: { code: string | readonly string[]; children: ReactNode }) {
  const { canAny } = usePermission();
  const codes = typeof code === "string" ? [code] : code;

  if (!canAny(codes)) return <Forbidden />;
  return <>{children}</>;
}

/**
 * ПОС унтраалттай үед кассын замууд хаагдана.
 *
 * Цэснээс нуугдсан ч хаягаар шууд орох боломж үлдэхээс сэргийлнэ —
 * түгээгчийн горимд бүх борлуулалт зөвхөн өдрийн хаалтаар бүртгэгдэнэ.
 */
function RequirePos({ children }: { children: ReactNode }) {
  const { enabled, loading } = usePosEnabled();

  if (loading) return <RouteFallback />;
  if (!enabled) return <PosDisabled />;
  return <>{children}</>;
}

function PosDisabled() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center gap-5 text-center">
      <span className="flex h-20 w-20 items-center justify-center rounded-full bg-warning-soft text-warning-dark">
        <PowerOff className="h-10 w-10" />
      </span>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-ink">{t.pos.disabled}</h1>
        <p className="max-w-md text-ink-soft">{t.pos.disabledHint}</p>
      </div>
      <Button variant="secondary" size="lg" onClick={() => navigate("/shift", { replace: true })}>
        {t.nav.shift}
      </Button>
    </div>
  );
}

/** Дүрийн дагуу нүүр дэлгэц рүү. */
function HomeRedirect() {
  const roleCode = useAuthStore((state) => state.user?.role_code ?? null);
  return <Navigate to={homeForRole(roleCode)} replace />;
}

function RouteFallback() {
  return (
    <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
      <Spinner size="lg" label={t.common.loading} />
    </div>
  );
}

// --- Замын хүснэгт --------------------------------------------------------

export function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<HomeRedirect />} />

          {/* Касс — тохиргоонд ПОС унтраалттай бол бүхэлдээ хаагдана */}
          <Route
            path="/pos"
            element={
              <RequirePermission code="sales.create">
                <RequirePos>
                  <PosPage />
                </RequirePos>
              </RequirePermission>
            }
          />
          <Route
            path="/pos/store"
            element={
              <RequirePermission code="sales.create">
                <RequirePos>
                  <PosStorePage />
                </RequirePos>
              </RequirePermission>
            }
          />
          <Route
            path="/pos/bulk"
            element={
              <RequirePermission code="sales.create">
                <RequirePos>
                  <PosBulkPage />
                </RequirePos>
              </RequirePermission>
            }
          />
          <Route
            path="/pos/payment"
            element={
              <RequirePermission code="sales.create">
                <RequirePos>
                  <PosPaymentPage />
                </RequirePos>
              </RequirePermission>
            }
          />

          {/* Ээлж */}
          <Route
            path="/shift"
            element={
              <RequirePermission code={["shifts.open", "shifts.close", "shifts.view_all"]}>
                <ShiftPage />
              </RequirePermission>
            }
          />
          <Route
            path="/shift/report/:id"
            element={
              <RequirePermission code={["shifts.close", "shifts.view_all"]}>
                <ShiftReportPage />
              </RequirePermission>
            }
          />
          <Route
            path="/daily-closings"
            element={
              <RequirePermission code={["shifts.close", "shifts.view_all"]}>
                <DailyClosingsPage />
              </RequirePermission>
            }
          />

          {/* Хяналтын самбар */}
          <Route
            path="/dashboard"
            element={
              <RequirePermission code="sales.view">
                <DashboardPage />
              </RequirePermission>
            }
          />
          <Route
            path="/owner"
            element={
              <RequirePermission code="dashboard.owner">
                <OwnerDashboardPage />
              </RequirePermission>
            }
          />

          {/* Сав */}
          <Route
            path="/tanks"
            element={
              <RequirePermission code="tanks.view">
                <TanksPage />
              </RequirePermission>
            }
          />
          <Route
            path="/tanks/:id"
            element={
              <RequirePermission code="tanks.view">
                <TankDetailPage />
              </RequirePermission>
            }
          />

          {/* Худалдан авалт */}
          {/* Шатахуун таталт нь Худалдан авалттай нэгдсэн — хуучин
              хадгалсан линкүүд шинэ цэс рүү чиглэнэ. */}
          <Route path="/receipts/fuel" element={<Navigate to="/purchases" replace />} />
          <Route path="/receipts/fuel/new" element={<Navigate to="/purchases/new" replace />} />
          <Route
            path="/payroll"
            element={
              <RequirePermission code="payroll.manage">
                <PayrollPage />
              </RequirePermission>
            }
          />
          <Route
            path="/employees"
            element={
              <RequirePermission code="payroll.manage">
                <EmployeesPage />
              </RequirePermission>
            }
          />
          <Route
            path="/report-center"
            element={
              <RequirePermission code="reports.view">
                <ReportCenterPage />
              </RequirePermission>
            }
          />
          <Route
            path="/reports/inventory"
            element={
              <RequirePermission code="reports.view">
                <InventoryReportPage />
              </RequirePermission>
            }
          />
          <Route
            path="/expenses"
            element={
              <RequirePermission code="expenses.manage">
                <ExpensesPage />
              </RequirePermission>
            }
          />
          <Route
            path="/bank-accounts"
            element={
              <RequirePermission code="bank.manage">
                <BankAccountsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/bank-statements"
            element={
              <RequirePermission code="bank.manage">
                <BankStatementsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/purchases"
            element={
              <RequirePermission code="purchases.manage">
                <PurchasesPage />
              </RequirePermission>
            }
          />
          {/* Нэгдсэн орлого — шатахуун + бараа нэг маягтаар. */}
          <Route
            path="/purchases/new"
            element={
              <RequirePermission code="purchases.manage">
                <ReceiveNewPage />
              </RequirePermission>
            }
          />
          {/* Зөвхөн барааны хуучин маягт — шууд линкээр орж болно. */}
          <Route
            path="/purchases/new/goods"
            element={
              <RequirePermission code="purchases.manage">
                <PurchaseNewPage />
              </RequirePermission>
            }
          />
          <Route
            path="/suppliers"
            element={
              <RequirePermission code="suppliers.manage">
                <SuppliersPage />
              </RequirePermission>
            }
          />

          {/* Бараа, нөөц */}
          <Route
            path="/products"
            element={
              <RequirePermission code="products.view">
                <ProductsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/inventory"
            element={
              <RequirePermission code="inventory.manage">
                <InventoryPage />
              </RequirePermission>
            }
          />
          <Route
            path="/price-changes"
            element={
              <RequirePermission code={["prices.request", "prices.approve"]}>
                <PriceChangesPage />
              </RequirePermission>
            }
          />

          {/* Харилцагч */}
          <Route
            path="/customers"
            element={
              <RequirePermission code="contracts.manage">
                <CustomersPage />
              </RequirePermission>
            }
          />
          <Route
            path="/contracts"
            element={
              <RequirePermission code="contracts.manage">
                <ContractsPage />
              </RequirePermission>
            }
          />

          {/* Борлуулалт */}
          <Route
            path="/sales"
            element={
              <RequirePermission code="sales.view">
                <SalesPage />
              </RequirePermission>
            }
          />
          <Route
            path="/sales/:id"
            element={
              <RequirePermission code="sales.view">
                <SaleDetailPage />
              </RequirePermission>
            }
          />
          <Route
            path="/sales/:id/refund"
            element={
              <RequirePermission code={["sales.refund.request", "sales.refund.approve"]}>
                <RefundPage />
              </RequirePermission>
            }
          />

          {/* Батлах, тайлан, НББ */}
          <Route
            path="/approvals"
            element={
              <RequirePermission code={["prices.approve", "sales.refund.approve"]}>
                <ApprovalsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/reports"
            element={
              <RequirePermission code="reports.view">
                <ReportsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/reports/financial"
            element={
              <RequirePermission code="accounting.view">
                <FinancialReportsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/accounting"
            element={
              <RequirePermission code="accounting.view">
                <AccountingPage />
              </RequirePermission>
            }
          />
          <Route
            path="/accounting/journal"
            element={
              <RequirePermission code="accounting.view">
                <JournalPage />
              </RequirePermission>
            }
          />
          <Route
            path="/accounting/apar"
            element={
              <RequirePermission code="accounting.view">
                <ApArPage />
              </RequirePermission>
            }
          />

          {/* Удирдлага */}
          <Route
            path="/branches"
            element={
              <RequirePermission code="settings.manage">
                <BranchesPage />
              </RequirePermission>
            }
          />
          <Route
            path="/branches/:branchId"
            element={
              <RequirePermission code="settings.manage">
                <BranchSetupPage />
              </RequirePermission>
            }
          />
          <Route
            path="/users"
            element={
              <RequirePermission code="users.manage">
                <UsersPage />
              </RequirePermission>
            }
          />
          <Route
            path="/audit"
            element={
              <RequirePermission code="audit.view">
                <AuditPage />
              </RequirePermission>
            }
          />
          <Route
            path="/settings"
            element={
              <RequirePermission code="settings.manage">
                <SettingsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/backup"
            element={
              <RequirePermission code="backup.manage">
                <BackupPage />
              </RequirePermission>
            }
          />

          <Route path="*" element={<NotFoundPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

export default AppRoutes;
