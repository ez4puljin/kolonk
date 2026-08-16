import { HardHat } from "lucide-react";

import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { t } from "../i18n/mn";

/**
 * Түр орлуулагч дэлгэц.
 *
 * Router нь бодит хуудсыг олохгүй үед (өөр багийн WP хараахан нэмээгүй)
 * үүнийг зурна. Бодит файл нэмэгдмэгц автоматаар солигдоно.
 */
export function Placeholder() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.errors.preparing} />
      <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-line-strong bg-white">
        <EmptyState
          icon={<HardHat className="h-7 w-7" />}
          title={t.errors.preparing}
          hint={t.errors.preparingHint}
        />
      </div>
    </div>
  );
}

export default Placeholder;
