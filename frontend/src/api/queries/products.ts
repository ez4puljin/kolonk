import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Paged,
  Product,
  ProductCategory,
  ProductCategoryCreate,
  ProductCreate,
  ProductSaleMode,
  ProductUpdate,
  UUID,
} from "../types";
import { searchIsActive } from "./_params";

export interface ProductListParams {
  q?: string;
  category_id?: UUID;
  /** ПОС: үлдэгдэл, үнийг энэ салбарынхаар харуулна. */
  branch_id?: UUID;
  active_only?: boolean;
  low_stock?: boolean;
  /** Ширхэг (`piece`) эсвэл задлан (`bulk`) бараа. */
  sale_mode?: ProductSaleMode;
  /** Зөвхөн задлан хөрвүүлж болох ширхэг бараа. */
  convertible?: boolean;
  limit?: number;
  offset?: number;
}

export const productKeys = {
  all: ["products"] as const,
  list: (params?: ProductListParams) => ["products", "list", params ?? {}] as const,
  detail: (id: UUID) => ["products", "detail", id] as const,
  byBarcode: (barcode: string) => ["products", "barcode", barcode] as const,
  categories: () => ["product-categories"] as const,
};

export function useProducts(params?: ProductListParams) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => api.get<Paged<Product>>("/api/products", { params: searchIsActive(params) }),
    staleTime: 60_000,
  });
}

export function useProduct(id: UUID | null | undefined) {
  return useQuery({
    queryKey: productKeys.detail(id ?? ""),
    queryFn: () => api.get<Product>(`/api/products/${id}`),
    enabled: Boolean(id),
  });
}

/** Штрих кодоор бараа хайх (кассын сканнер). */
export function useProductByBarcode(barcode: string | null) {
  return useQuery({
    queryKey: productKeys.byBarcode(barcode ?? ""),
    // Тусдаа barcode endpoint байхгүй — /api/products хайлт нь нэр, SKU,
    // штрих кодыг зэрэг тулгадаг тул түүнийг ашиглана.
    queryFn: () =>
      api.get<Paged<Product>>("/api/products", {
        params: { search: barcode, limit: 1 },
      }),
    enabled: Boolean(barcode && barcode.length >= 4),
    retry: false,
  });
}

export function useProductCategories() {
  return useQuery({
    queryKey: productKeys.categories(),
    queryFn: () => api.get<Paged<ProductCategory>>("/api/product-categories"),
    staleTime: 300_000,
  });
}

export function useCreateProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductCreate) => api.post<Product>("/api/products", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
  });
}

export function useUpdateProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ProductUpdate }) =>
      api.patch<Product>(`/api/products/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
  });
}

export function useDeleteProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/products/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.all });
    },
  });
}

export function useCreateCategoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductCategoryCreate) =>
      api.post<ProductCategory>("/api/product-categories", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.categories() });
    },
  });
}

export function useUpdateCategoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: Partial<ProductCategoryCreate> }) =>
      api.patch<ProductCategory>(`/api/product-categories/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.categories() });
    },
  });
}
