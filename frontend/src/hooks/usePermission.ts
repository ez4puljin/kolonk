import { useCallback } from "react";

import { useAuthStore } from "../stores/auth";

/**
 * Эрх шалгах.
 *
 * ```tsx
 * const { can } = usePermission();
 * if (!can("sales.refund.approve")) return null;
 * ```
 */
export function usePermission() {
  const permissions = useAuthStore((state) => state.permissions);
  const roleCode = useAuthStore((state) => state.user?.role_code ?? null);

  const can = useCallback((code: string) => permissions.includes(code), [permissions]);

  const canAny = useCallback(
    (codes: readonly string[]) => codes.length === 0 || codes.some((code) => permissions.includes(code)),
    [permissions],
  );

  const canAll = useCallback(
    (codes: readonly string[]) => codes.every((code) => permissions.includes(code)),
    [permissions],
  );

  return { can, canAny, canAll, permissions, roleCode };
}

/** Ганц эрхийн богино хувилбар. */
export function useCan(code: string): boolean {
  return useAuthStore((state) => state.permissions.includes(code));
}
