export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const SIZES: Record<NonNullable<SpinnerProps["size"]>, string> = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
};

export function Spinner({ size = "md", className = "", label }: SpinnerProps) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`} role="status" aria-live="polite">
      <span
        className={`${SIZES[size]} animate-spin rounded-full border-current border-t-transparent opacity-70`}
      />
      {label ? <span className="text-sm">{label}</span> : null}
    </span>
  );
}

export default Spinner;
