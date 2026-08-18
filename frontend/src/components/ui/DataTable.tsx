import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { t } from "../../i18n/mn";
import { EmptyState } from "./EmptyState";
import { Spinner } from "./Spinner";

export type ColumnAlign = "left" | "right" | "center";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: ColumnAlign;
  width?: string;
  /** 768px-ээс доош далдлах (гар утасны картад орохгүй). */
  hideOnMobile?: boolean;
  /** Картын гарчиг болох багана (мобайл). */
  primary?: boolean;
  /** Тоон багана — tabular-nums. */
  numeric?: boolean;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  empty?: ReactNode;
  emptyTitle?: string;
  footer?: ReactNode;
  /** Мөрд нэмэлт анги (анхааруулга өнгө гэх мэт). */
  rowClassName?: (row: T) => string;
  className?: string;
}

const ALIGN: Record<ColumnAlign, string> = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  loading = false,
  empty,
  emptyTitle,
  footer,
  rowClassName,
  className = "",
}: DataTableProps<T>) {
  // Хэвтээ гүйлт байгаа эсэхийг мэдэрч ирмэг дээр сүүдэр үзүүлнэ —
  // ингэснээр нуугдсан багана байгаа нь хэрэглэгчид шууд мэдэгдэнэ.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  const syncEdges = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setEdges({ left: el.scrollLeft > 2, right: max > 2 && el.scrollLeft < max - 2 });
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    syncEdges();
    const observer = new ResizeObserver(syncEdges);
    observer.observe(el);
    return () => observer.disconnect();
  }, [syncEdges, rows, columns]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (rows.length === 0) {
    return <>{empty ?? <EmptyState title={emptyTitle ?? t.common.empty} />}</>;
  }

  const primaryColumn = columns.find((column) => column.primary) ?? columns[0];
  /*
   * Үйлдлийн багана картан харагдацад ТУСДАА гарна.
   *
   * Өмнө нь бусад баганын хамт 2 баганат торны `truncate`-тай нүдэнд
   * ордог байсан тул товчнууд 0px болж таслагдаж, гар утаснаас ямар ч
   * хүснэгтийн үйлдэл (Засах, Идэвхгүй болгох гэх мэт) хийх боломжгүй
   * байв. Мөн мөр дарагддаг хүснэгтэд бүх карт `<button>` болдог тул
   * товч дотор товч үүсч, дотоод товч ажиллахгүй болдог байлаа.
   */
  const actionColumn = columns.find((column) => column.key === "actions");
  const mobileColumns = columns.filter(
    (column) =>
      column.key !== primaryColumn.key && column.key !== "actions" && !column.hideOnMobile,
  );
  const interactive = typeof onRowClick === "function";

  return (
    <div className={className}>
      {/* Дэлгэц ≥768px — хүснэгт */}
      <div className="relative hidden md:block">
        {edges.left ? (
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-6 bg-gradient-to-r from-black/10 to-transparent" />
        ) : null}
        {edges.right ? (
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-6 bg-gradient-to-l from-black/10 to-transparent" />
        ) : null}
        <div ref={scrollRef} onScroll={syncEdges} className="scroll-touch overflow-x-auto">
        <table className="w-full border-collapse text-[15px]">
          <thead>
            <tr className="border-b border-line-strong bg-surface-alt">
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  style={column.width ? { width: column.width } : undefined}
                  className={`px-3 py-3 text-xs font-bold tracking-wide text-ink-soft uppercase 2xl:px-4 ${ALIGN[column.align ?? "left"]}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={interactive ? () => onRowClick?.(row) : undefined}
                className={[
                  "border-b border-line last:border-b-0",
                  interactive ? "cursor-pointer transition-colors hover:bg-surface-alt" : "",
                  rowClassName?.(row) ?? "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={[
                      "px-3 py-3.5 align-middle 2xl:px-4",
                      ALIGN[column.align ?? "left"],
                      column.numeric ? "num whitespace-nowrap" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Дэлгэц <768px — карт */}
      <div className="flex flex-col gap-3 md:hidden">
        {rows.map((row) => {
          const body = (
            <>
              <div className="mb-2 text-base font-bold text-ink">{primaryColumn.render(row)}</div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                {mobileColumns.map((column) => (
                  <div key={column.key} className="flex min-w-0 flex-col">
                    <dt className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
                      {column.header}
                    </dt>
                    <dd className={`truncate text-sm text-ink ${column.numeric ? "num" : ""}`}>
                      {column.render(row)}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          );

          const shell = `rounded-xl border border-line bg-white px-4 py-3.5 text-left ${rowClassName?.(row) ?? ""}`;

          const actions = actionColumn ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
              {actionColumn.render(row)}
            </div>
          ) : null;

          return (
            <div key={rowKey(row)} className={shell}>
              {interactive ? (
                <button
                  type="button"
                  onClick={() => onRowClick?.(row)}
                  className="touch-target w-full text-left active:bg-surface-alt"
                >
                  {body}
                </button>
              ) : (
                body
              )}
              {actions}
            </div>
          );
        })}
      </div>

      {footer ? <div className="border-t border-line px-4 py-3">{footer}</div> : null}
    </div>
  );
}

export default DataTable;
