import { create } from "zustand";

export type ToastKind = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
  /** мс. 0 бол автоматаар хаагдахгүй. */
  timeout: number;
}

export interface NumPadRequest {
  /** Аль талбарыг засаж байгааг компонент таних түлхүүр. */
  target: string;
  title: string;
  /** Одоогийн утга (string decimal). */
  value: string;
  /** Аравтын цэг зөвшөөрөх эсэх. */
  allowDecimal: boolean;
  /** Дүнгийн ард харуулах нэгж ("₮", "л", "ш"). */
  suffix: string;
}

interface UiState {
  numpad: NumPadRequest | null;
  modals: string[];
  toasts: Toast[];
  sidebarOpen: boolean;

  openNumPad: (request: Partial<NumPadRequest> & { target: string }) => void;
  setNumPadValue: (value: string) => void;
  closeNumPad: () => void;

  pushModal: (id: string) => void;
  popModal: () => void;
  closeModal: (id: string) => void;
  isTopModal: (id: string) => boolean;

  pushToast: (message: string, kind?: ToastKind, timeout?: number) => string;
  toastSuccess: (message: string) => string;
  toastError: (message: string) => string;
  dismissToast: (id: string) => void;
  clearToasts: () => void;

  setSidebar: (open: boolean) => void;
  toggleSidebar: () => void;
}

let toastSeq = 0;

function nextToastId(): string {
  toastSeq += 1;
  return `toast-${Date.now().toString(36)}-${toastSeq}`;
}

export const useUiStore = create<UiState>()((set, get) => ({
  numpad: null,
  modals: [],
  toasts: [],
  sidebarOpen: false,

  openNumPad: (request) =>
    set({
      numpad: {
        target: request.target,
        title: request.title ?? "",
        value: request.value ?? "",
        allowDecimal: request.allowDecimal ?? true,
        suffix: request.suffix ?? "",
      },
    }),

  setNumPadValue: (value) =>
    set((state) => (state.numpad ? { numpad: { ...state.numpad, value } } : {})),

  closeNumPad: () => set({ numpad: null }),

  pushModal: (id) =>
    set((state) => (state.modals.includes(id) ? {} : { modals: [...state.modals, id] })),

  popModal: () => set((state) => ({ modals: state.modals.slice(0, -1) })),

  closeModal: (id) => set((state) => ({ modals: state.modals.filter((item) => item !== id) })),

  isTopModal: (id) => {
    const stack = get().modals;
    return stack.length > 0 && stack[stack.length - 1] === id;
  },

  pushToast: (message, kind = "info", timeout = 4000) => {
    const id = nextToastId();
    set((state) => ({ toasts: [...state.toasts, { id, kind, message, timeout }] }));
    if (timeout > 0 && typeof window !== "undefined") {
      window.setTimeout(() => get().dismissToast(id), timeout);
    }
    return id;
  },

  toastSuccess: (message) => get().pushToast(message, "success", 3000),

  toastError: (message) => get().pushToast(message, "error", 6000),

  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),

  clearToasts: () => set({ toasts: [] }),

  setSidebar: (open) => set({ sidebarOpen: open }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));

/** React-ээс гадуур toast харуулах (api алдаа боловсруулах гэх мэт). */
export function toast(message: string, kind: ToastKind = "info"): void {
  useUiStore.getState().pushToast(message, kind);
}
