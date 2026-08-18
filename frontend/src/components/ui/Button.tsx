import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "success" | "danger" | "warning" | "ghost" | "dark";
/**
 * sm = 40px, md = 48px, lg = 64px, xl = 80px.
 *
 * `sm` нь ЗӨВХӨН хүснэгтийн мөрийн үйлдэлд — тэнд олон товч зэрэгцэн
 * орох тул 48px нь мөрийг хэт бүдүүн болгодог. Түгээгчийн бээлийтэй
 * дардаг үндсэн товчнуудад `md`-ээс доош ашиглахгүй.
 */
export type ButtonSize = "sm" | "md" | "lg" | "xl";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  iconRight?: ReactNode;
  block?: boolean;
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-action text-white hover:bg-action-dark active:bg-action-dark border-transparent shadow-sm",
  secondary:
    "bg-white text-ink hover:bg-surface-alt active:bg-surface-sunken border-line-strong shadow-sm",
  success: "bg-success text-white hover:bg-success-dark active:bg-success-dark border-transparent shadow-sm",
  danger: "bg-danger text-white hover:bg-danger-dark active:bg-danger-dark border-transparent shadow-sm",
  warning: "bg-warning text-brand-900 hover:bg-warning-dark active:bg-warning-dark border-transparent",
  ghost: "bg-transparent text-ink hover:bg-surface-alt active:bg-surface-sunken border-transparent",
  dark: "bg-brand-800 text-ink-invert hover:bg-brand-700 active:bg-brand-700 border-brand-700",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-10 min-h-10 px-3 text-sm rounded-lg gap-2",
  md: "h-12 min-h-12 px-5 text-[15px] rounded-xl gap-2.5",
  lg: "h-16 min-h-16 px-7 text-lg rounded-xl gap-3",
  xl: "h-20 min-h-20 px-9 text-2xl rounded-2xl gap-3.5",
};

const ICON_SIZE: Record<ButtonSize, string> = {
  sm: "[&_svg]:h-4 [&_svg]:w-4",
  md: "[&_svg]:h-5 [&_svg]:w-5",
  lg: "[&_svg]:h-6 [&_svg]:w-6",
  xl: "[&_svg]:h-7 [&_svg]:w-7",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    icon,
    iconRight,
    block = false,
    className = "",
    disabled,
    children,
    type = "button",
    ...rest
  },
  ref,
) {
  const isDisabled = disabled === true || loading;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={[
        "inline-flex items-center justify-center border font-semibold transition-colors duration-100",
        "select-none touch-manipulation",
        "disabled:opacity-45 disabled:pointer-events-none",
        "focus-visible:outline-3 focus-visible:outline-offset-2",
        VARIANTS[variant],
        SIZES[size],
        ICON_SIZE[size],
        // Бичиггүй, зөвхөн дүрстэй товч дөрвөлжин болно.
        children ? "" : "aspect-square px-0",
        block ? "w-full" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {loading ? <Spinner size={size === "lg" || size === "xl" ? "md" : "sm"} /> : icon}
      {children ? <span className="truncate">{children}</span> : null}
      {iconRight}
    </button>
  );
});

export default Button;
