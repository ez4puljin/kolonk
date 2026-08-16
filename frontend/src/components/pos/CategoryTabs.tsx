import type { ProductCategory, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { TabBar, type TabItem } from "../ui/TabBar";

/** "" = бүх ангилал. */
export const ALL_CATEGORIES = "";

export interface CategoryTabsProps {
  categories: readonly ProductCategory[];
  value: UUID | "";
  onChange: (value: UUID | "") => void;
  className?: string;
}

export function CategoryTabs({ categories, value, onChange, className = "" }: CategoryTabsProps) {
  const items: TabItem<string>[] = [
    { value: ALL_CATEGORIES, label: t.pos.allCategories },
    ...categories.map((category) => ({
      value: category.id,
      label: category.name_mn,
      badge: category.product_count ?? null,
    })),
  ];

  return (
    <TabBar<string>
      value={value}
      onChange={(next) => onChange(next as UUID | "")}
      items={items}
      variant="pill"
      className={className}
    />
  );
}

export default CategoryTabs;
