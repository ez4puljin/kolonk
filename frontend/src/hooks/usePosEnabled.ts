import { useSettings } from "../api/queries/system";

/**
 * ПОС борлуулалт асаалттай эсэх — цэс, товч, замын хамгаалалт бүгд үүнийг харна.
 *
 * Тохиргоо ачаалагдаж дуустал `true` буцаана: тохиргоо ирэхээс өмнө цэс
 * анивчиж алга болохоос сэргийлнэ. `loading` талбараар замын хамгаалалт
 * шийдвэрээ хойшлуулна.
 */
export function usePosEnabled(): { enabled: boolean; loading: boolean } {
  const { data, isLoading } = useSettings();
  if (data === undefined) return { enabled: true, loading: isLoading };
  return {
    enabled: data.pos_sales_enabled === true || data.pos_sales_enabled === "true",
    loading: false,
  };
}
