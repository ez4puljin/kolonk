/**
 * Админ панел → Түлш: станцад зарагдах түлшний төрлүүд (бүх салбарт нийтлэг).
 * Салбар бүрийн үнийг Салбарын тохиргоо → Түлш табаас харна.
 */
import { FuelsPanel } from "../../components/admin/FuelsPanel";
import { PageHeader } from "../../components/layout/PageHeader";
import { t } from "../../i18n/mn";

export function AdminFuelsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.fuels.title} subtitle={t.fuels.subtitle} />
      <FuelsPanel />
    </div>
  );
}

export default AdminFuelsPage;
