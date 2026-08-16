import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

import { t } from "../../i18n/mn";

export interface EmptyStateProps {
  title?: string;
  hint?: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  title = t.common.empty,
  hint = t.common.emptyHint,
  icon,
  action,
  compact = false,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${compact ? "gap-2 py-8" : "gap-3 py-16"} ${className}`}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
        {icon ?? <Inbox className="h-7 w-7" />}
      </span>
      <div className="text-base font-semibold text-ink">{title}</div>
      {hint ? <div className="max-w-sm text-sm text-ink-soft">{hint}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export default EmptyState;
