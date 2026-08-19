/**
 * Төвлөрсөн HTTP клиент (CONTRACTS.md §8-9).
 *
 * - JWT-г auth store-оос автоматаар `Authorization: Bearer` толгойд нэмнэ.
 * - Серверийн монгол `detail`-ыг `ApiError.detail`-д хүргэнэ.
 * - 401 → нэвтрэлт цэвэрлээд `/login` рүү шилжинэ (silent горимоос бусад үед).
 */

import { t } from "../i18n/mn";
import { clearSession, getToken } from "../stores/auth";

export const API_BASE = "";
export const LOGIN_PATH = "/login";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly payload: unknown;

  constructor(status: number, detail: string, payload: unknown = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }

  get isNetwork(): boolean {
    return this.status === 0;
  }

  get isAuth(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** Бизнес логикийн алдаа — хэрэглэгчид шууд харуулна. */
  get isBusiness(): boolean {
    return this.status === 422;
  }
}

export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue | QueryValue[]>;

/** `{a: 1, b: undefined}` → `"?a=1"`. Хоосон утгыг алгасана. */
export function buildQuery(params?: QueryParams): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, raw] of Object.entries(params)) {
    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (value === null || value === undefined || value === "") continue;
      search.append(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export interface RequestOptions {
  /** Query параметр — URL-д автоматаар нэмэгдэнэ. */
  params?: QueryParams;
  /** Нэмэлт толгой. */
  headers?: Record<string, string>;
  /** Хүсэлт цуцлах. */
  signal?: AbortSignal;
  /** Үнэн бол 401 үед сесс цэвэрлэхгүй, /login рүү шилжүүлэхгүй. */
  silent?: boolean;
  /** Токен хавсаргахгүй (нэвтрэх дэлгэцийн нээлттэй хүсэлт). */
  anonymous?: boolean;
}

interface InternalOptions extends RequestOptions {
  method: string;
  body?: unknown;
}

function detailFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim() !== "") return payload;
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim() !== "") return detail;
    // FastAPI-ийн валидацийн алдаа: detail = [{msg, loc}, ...]
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string"
            ? (item as { msg: string }).msg
            : null,
        )
        .filter((msg): msg is string => msg !== null);
      if (messages.length > 0) return messages.join("; ");
    }
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim() !== "") return message;
  }
  return fallback;
}

function fallbackDetail(status: number): string {
  if (status === 401) return t.auth.sessionExpired;
  if (status === 403) return t.errors.forbidden;
  if (status === 404) return t.errors.notFound;
  if (status === 422) return t.errors.validation;
  if (status >= 500) return t.errors.server;
  return t.errors.unknown;
}

function handleUnauthorized(): void {
  clearSession();
  if (typeof window !== "undefined" && window.location.pathname !== LOGIN_PATH) {
    window.location.assign(LOGIN_PATH);
  }
}

async function request<T>(path: string, options: InternalOptions): Promise<T> {
  const { method, body, params, headers, signal, silent, anonymous } = options;

  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (!anonymous) {
    const token = getToken();
    if (token) requestHeaders.Authorization = `Bearer ${token}`;
  }

  const init: RequestInit = { method, headers: requestHeaders, signal };
  if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(params)}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, t.errors.network, error);
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  let payload: unknown = null;
  if (contentType.includes("application/json")) {
    payload = await response.json().catch(() => null);
  } else {
    const text = await response.text().catch(() => "");
    payload = text === "" ? null : text;
  }

  if (!response.ok) {
    if (response.status === 401 && !silent) handleUnauthorized();
    throw new ApiError(response.status, detailFromPayload(payload, fallbackDetail(response.status)), payload);
  }

  return payload as T;
}

/** Файл илгээх (multipart) — гэрээний PDF гэх мэт. */
export async function upload<T>(path: string, file: File, fieldName = "file"): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const form = new FormData();
  form.append(fieldName, file, file.name);

  let response: Response;
  try {
    // Content-Type-ийг browser өөрөө boundary-тай нь тавина — гараар бичихгүй.
    response = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form });
  } catch (error) {
    throw new ApiError(0, t.errors.network, error);
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) handleUnauthorized();
    throw new ApiError(response.status, detailFromPayload(payload, fallbackDetail(response.status)), payload);
  }
  return payload as T;
}

/** Хоёртын файл татах (Excel тайлан, нөөцлөлт). */
export async function download(path: string, params?: QueryParams, filename?: string): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(params)}`, { headers });
  } catch (error) {
    throw new ApiError(0, t.errors.network, error);
  }

  if (!response.ok) {
    if (response.status === 401) handleUnauthorized();
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, detailFromPayload(payload, fallbackDetail(response.status)), payload);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename ?? path.split("/").pop() ?? "download";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * Хамгаалалттай эндпойнтоос файл татаад блоб URL болгоно.
 *
 * `<img src>` нь `Authorization` толгой явуулж чаддаггүй тул зургийг эхлээд
 * токентой татаж, санах ойн URL үүсгэнэ. Дуусахад `URL.revokeObjectURL`-ээр
 * чөлөөлөх нь ДУУДАГЧИЙН үүрэг — эс бөгөөс блоб хуудас хаагдтал үлдэнэ.
 */
export async function blobUrl(path: string): Promise<string> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers });
  } catch (error) {
    throw new ApiError(0, t.errors.network, error);
  }
  if (!response.ok) {
    if (response.status === 401) handleUnauthorized();
    throw new ApiError(response.status, fallbackDetail(response.status));
  }
  return URL.createObjectURL(await response.blob());
}

export const api = {
  get: <T>(path: string, options?: RequestOptions): Promise<T> =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    request<T>(path, { ...options, method: "POST", body: body ?? {} }),

  patch: <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    request<T>(path, { ...options, method: "PATCH", body: body ?? {} }),

  put: <T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    request<T>(path, { ...options, method: "PUT", body: body ?? {} }),

  del: <T>(path: string, options?: RequestOptions): Promise<T> =>
    request<T>(path, { ...options, method: "DELETE" }),

  upload,
  download,
};

/** Дурын алдааг хэрэглэгчид харуулах монгол мөр болгоно. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return t.errors.unknown;
}
