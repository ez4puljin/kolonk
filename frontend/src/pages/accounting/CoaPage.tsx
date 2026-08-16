/**
 * Дансны төлөвлөгөө (WP12) — `parent_code`-оор мод болгон эрэмбэлж,
 * төрлийн тэмдэг ба өнөөгийн үлдэгдлийг харуулна.
 *
 * Сервер: `/api/accounting/accounts`, `/api/accounting/trial-balance`.
 */

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { useAccounts, useTrialBalance } from "../../api/queries/accounting";
import type { Account } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar, type TabItem } from "../../components/ui/TabBar";
import { t } from "../../i18n/mn";
import type { Tone } from "../../lib/constants";
import { dIsZero } from "../../lib/decimal";
import { formatDate, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";

const ACCOUNT_TYPE_MN: Record<string, string> = {
  asset: t.accounting.accountTypes.asset,
  liability: t.accounting.accountTypes.liability,
  equity: t.accounting.accountTypes.equity,
  revenue: t.accounting.accountTypes.revenue,
  expense: t.accounting.accountTypes.expense,
};

const ACCOUNT_TYPE_TONE: Record<string, Tone> = {
  asset: "action",
  liability: "warning",
  equity: "brand",
  revenue: "success",
  expense: "danger",
};

type TypeFilter = "all" | "asset" | "liability" | "equity" | "revenue" | "expense";

const TYPE_TABS: readonly TabItem<TypeFilter>[] = [
  { value: "all", label: t.common.all },
  { value: "asset", label: t.accounting.accountTypes.asset },
  { value: "liability", label: t.accounting.accountTypes.liability },
  { value: "equity", label: t.accounting.accountTypes.equity },
  { value: "revenue", label: t.accounting.accountTypes.revenue },
  { value: "expense", label: t.accounting.accountTypes.expense },
];

interface TreeNode {
  account: Account;
  depth: number;
}

const MAX_DEPTH = 6;

/** `parent_code`-оор эцэг-хүүхдийн дараалалд буулгана (цикл хамгаалалттай). */
function buildTree(accounts: readonly Account[]): TreeNode[] {
  const codes = new Set(accounts.map((account) => account.code));
  const children = new Map<string, Account[]>();

  for (const account of accounts) {
    const parent =
      account.parent_code && account.parent_code !== account.code && codes.has(account.parent_code)
        ? account.parent_code
        : "";
    const bucket = children.get(parent);
    if (bucket) bucket.push(account);
    else children.set(parent, [account]);
  }

  for (const bucket of children.values()) {
    bucket.sort((a, b) => a.sort_order - b.sort_order || a.code.localeCompare(b.code));
  }

  const seen = new Set<string>();
  const flat: TreeNode[] = [];

  const walk = (parent: string, depth: number): void => {
    if (depth > MAX_DEPTH) return;
    for (const account of children.get(parent) ?? []) {
      if (seen.has(account.code)) continue;
      seen.add(account.code);
      flat.push({ account, depth });
      walk(account.code, depth + 1);
    }
  };

  walk("", 0);

  // Мод руу орж чадаагүй данс байвал (эцэг нь дутуу) төгсгөлд нь нэмнэ.
  for (const account of accounts) {
    if (!seen.has(account.code)) flat.push({ account, depth: 0 });
  }

  return flat;
}

export function CoaPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");

  const asOf = todayInput();
  const accountsQuery = useAccounts(false);
  const trialQuery = useTrialBalance(asOf);

  const balances = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of trialQuery.data?.accounts ?? []) map.set(row.code, row.balance);
    return map;
  }, [trialQuery.data]);

  const nodes = useMemo(() => buildTree(accountsQuery.data ?? []), [accountsQuery.data]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return nodes.filter((node) => {
      if (typeFilter !== "all" && node.account.account_type !== typeFilter) return false;
      if (needle === "") return true;
      return (
        node.account.code.toLowerCase().includes(needle) ||
        node.account.name_mn.toLowerCase().includes(needle)
      );
    });
  }, [nodes, search, typeFilter]);

  const trial = trialQuery.data;
  const balanced = trial ? dIsZero(trial.imbalance) : true;

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.accounting.accounts}
        subtitle={`${t.accounting.asOf} ${formatDate(asOf)}`}
      >
        <div className="flex flex-col gap-3">
          <TabBar value={typeFilter} onChange={setTypeFilter} items={TYPE_TABS} />
          <label className="relative flex max-w-md items-center">
            <Search className="pointer-events-none absolute left-4 h-5 w-5 text-ink-faint" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.common.searchPlaceholder}
              aria-label={t.common.search}
              className="h-12 w-full rounded-xl border border-line-strong bg-white pr-4 pl-12 text-[15px] text-ink focus:border-action focus:outline-none"
            />
          </label>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatBox label={t.accounting.totalDebit} value={formatMNT(trial?.total_debit ?? "0")} tone="action" />
        <StatBox label={t.accounting.totalCredit} value={formatMNT(trial?.total_credit ?? "0")} tone="action" />
        <StatBox
          label={t.accounting.imbalance}
          value={formatMoneyExact(trial?.imbalance ?? "0")}
          tone={balanced ? "success" : "danger"}
          hint={balanced ? t.accounting.balanced : t.accounting.notBalanced}
        />
      </div>

      <Card title={t.accounting.accounts} subtitle={`${visible.length} ${t.common.rows}`} flush>
        {accountsQuery.isLoading ? (
          <div className="flex justify-center py-16 text-ink-soft">
            <Spinner size="lg" label={t.common.loading} />
          </div>
        ) : visible.length === 0 ? (
          <EmptyState title={t.common.empty} hint={t.common.emptyHint} />
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {visible.map(({ account, depth }) => {
              const balance = balances.get(account.code);
              return (
                <li
                  key={account.id}
                  className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5"
                  style={{ paddingLeft: `${16 + Math.min(depth, MAX_DEPTH) * 14}px` }}
                >
                  {depth > 0 ? (
                    <span
                      className="h-6 w-0.5 shrink-0 rounded-full bg-line-strong"
                      aria-hidden="true"
                    />
                  ) : null}

                  <span className="num shrink-0 text-[15px] font-bold text-ink">{account.code}</span>

                  <span
                    className={`min-w-0 flex-1 truncate text-[15px] ${
                      account.is_postable ? "text-ink" : "font-semibold text-ink-soft"
                    }`}
                  >
                    {account.name_mn}
                  </span>

                  <StatusBadge
                    size="sm"
                    tone={ACCOUNT_TYPE_TONE[account.account_type] ?? "neutral"}
                    label={ACCOUNT_TYPE_MN[account.account_type] ?? account.account_type}
                  />

                  {!account.is_postable ? (
                    <StatusBadge size="sm" tone="neutral" label="Бүлэг" />
                  ) : null}

                  <span className="num w-full shrink-0 text-right text-[15px] font-bold text-ink sm:w-40">
                    {balance === undefined ? "—" : formatMNT(balance)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default CoaPage;
