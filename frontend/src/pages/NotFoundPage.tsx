import { useNavigate } from "react-router-dom";
import { Compass } from "lucide-react";

import { Button } from "../components/ui/Button";
import { t } from "../i18n/mn";
import { homeForRole } from "../lib/constants";
import { useAuthStore } from "../stores/auth";

export function NotFoundPage() {
  const navigate = useNavigate();
  const roleCode = useAuthStore((state) => state.user?.role_code ?? null);
  const token = useAuthStore((state) => state.token);

  const goHome = (): void => {
    navigate(token ? homeForRole(roleCode) : "/login", { replace: true });
  };

  return (
    <div className="flex min-h-[70vh] flex-1 flex-col items-center justify-center gap-6 text-center">
      <span className="flex h-24 w-24 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
        <Compass className="h-12 w-12" />
      </span>

      <div className="space-y-2">
        <div className="num text-6xl font-black text-line-strong">404</div>
        <h1 className="text-2xl font-bold text-ink">{t.errors.notFound}</h1>
        <p className="max-w-md text-ink-soft">{t.errors.notFoundHint}</p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button variant="secondary" size="lg" onClick={() => navigate(-1)}>
          {t.common.back}
        </Button>
        <Button variant="primary" size="lg" onClick={goHome}>
          {t.errors.goHome}
        </Button>
      </div>
    </div>
  );
}

export default NotFoundPage;
