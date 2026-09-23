/**
 * Админ/нягтлангийн анхааруулга — үнэ батлагдсан ч түгээгч үнийн тэмдэглэл
 * оруулаагүй нээлттэй ээлжүүд. Хяналтын самбар, үнийн өөрчлөлт, батлах
 * хуудсанд харагдана; минут тутам шинэчлэгдэнэ, бүх тэмдэглэл ормогц алга болно.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, Droplets } from "lucide-react";

import { useOpenShiftPriceAlerts } from "../../api/queries/shifts";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { formatNumber } from "../../lib/format";
import { PriceMarkModal } from "../../pages/shift/AttendantShiftPage";
import { Button } from "../ui/Button";

export function OpenShiftPriceAlerts() {
  const navigate = useNavigate();
  const { canAny } = usePermission();
  const allowed = canAny(["shifts.view_all", "prices.approve"]);
  const { data } = useOpenShiftPriceAlerts(allowed);
  const [target, setTarget] = useState<{ shiftId: string; nozzleId: string; price: string } | null>(null);
  if (!allowed || !data || data.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border-2 border-warning bg-warning-soft px-4 py-3 text-warning-dark">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0" />
        <div className="flex flex-col gap-1">
          <span className="text-base font-bold">{t.attendant.adminPriceAlertTitle}</span>
          <span className="text-sm">{t.attendant.adminPriceAlertHint}</span>
        </div>
      </div>
      {data.map((shift) => (
        <div key={shift.shift_id} className="flex flex-col gap-2 rounded-xl border border-warning bg-surface px-3 py-2 text-ink">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-bold">
              {t.attendant.adminPriceAlertShift
                .replace("{n}", String(shift.shift_number))
                .replace("{branch}", shift.branch_name || "—")
                .replace("{who}", shift.attendant || "—")}
            </span>
            <Button
              variant="secondary"
              size="sm"
              icon={<ArrowRight />}
              onClick={() => navigate(`/shift/report/${shift.shift_id}`)}
            >
              {t.attendant.adminPriceAlertOpen}
            </Button>
          </div>
          <ul className="num flex flex-col gap-2 text-sm text-ink-soft">
            {shift.alerts.map((alert) => (
              <li key={alert.nozzle_id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {alert.pump_name} · №{alert.nozzle_number} {alert.fuel_name} —{" "}
                  {t.attendant.priceAlertRow
                    .replace("{used}", formatNumber(alert.used_price))
                    .replace("{now}", formatNumber(alert.current_price))}
                  {alert.has_mark ? <span className="ml-1 text-danger-dark">({t.attendant.priceAlertWrongMark})</span> : null}
                </span>
                {/* Админ/нягтлан түгээгчийн өмнөөс тэмдэглэл оруулж болно (сервер shifts.view_all-д зөвшөөрдөг). */}
                <Button
                  variant="warning"
                  size="sm"
                  icon={<Droplets />}
                  onClick={() => setTarget({ shiftId: shift.shift_id, nozzleId: alert.nozzle_id, price: alert.current_price })}
                >
                  {t.attendant.priceAlertAction}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {target ? (
        <PriceMarkModal
          shiftId={target.shiftId}
          open
          onClose={() => setTarget(null)}
          initialNozzleId={target.nozzleId}
          initialPrice={target.price}
        />
      ) : null}
    </div>
  );
}
