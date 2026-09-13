/**
 * Түлш — ажлын системийн хуудас (нягтлан/менежерт).
 *
 * Админ панелийн эрхтэй хэрэглэгч энд орвол `/admin/fuels` руу шилжинэ —
 * түлшний тохиргоо админд нэг газраа байг.
 */
import { Navigate } from "react-router-dom";

import { FuelsPanel } from "../../components/admin/FuelsPanel";
import { PageHeader } from "../../components/layout/PageHeader";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";

export function FuelsPage() {
  const isAdmin = useCan("settings.manage");
  if (isAdmin) return <Navigate to="/admin/fuels" replace />;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.fuels.title} subtitle={t.fuels.subtitle} />
      <FuelsPanel />
    </div>
  );
}

export default FuelsPage;
