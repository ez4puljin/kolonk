/**
 * Түлш — ажлын системийн хуудас (нягтлан/менежерт).
 *
 * Админ салбар бүрийн түлшийг Админ панел → Салбарын тохиргоо → «Түлш»
 * табаас тохируулна; энд бүх салбарт нийтлэг төрлүүд, үндсэн үнэ харагдана.
 */
import { FuelsPanel } from "../../components/admin/FuelsPanel";
import { PageHeader } from "../../components/layout/PageHeader";
import { t } from "../../i18n/mn";

export function FuelsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.fuels.title} subtitle={t.fuels.subtitle} />
      <FuelsPanel />
    </div>
  );
}

export default FuelsPage;
