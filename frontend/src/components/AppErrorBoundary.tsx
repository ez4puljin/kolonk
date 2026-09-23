import { Component, type ErrorInfo, type ReactNode } from "react";

import { isChunkLoadError, reloadForNewVersion } from "../lib/staleBuild";

/**
 * Програмын хамгийн гадна талын алдаа баригч.
 *
 * Өмнө нь ямар нэг хуудас унахад React бүх модыг устгаж, хэрэглэгч (ялангуяа
 * утсан дээр) ямар ч тайлбаргүй хар дэлгэц хардаг байв. Одоо ойлгомжтой
 * мессеж, «Дахин ачаалах» товч харуулна. Шинэ хувилбараас болсон бол шууд
 * дахин ачаална.
 */
export class AppErrorBoundary extends Component<{ children: ReactNode }, { error: unknown }> {
  state: { error: unknown } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    if (isChunkLoadError(error) && reloadForNewVersion()) return;
    console.error("Програмын алдаа", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-surface px-6 py-16 text-center">
        <div className="text-5xl">⚠️</div>
        <h1 className="text-2xl font-bold text-ink">Алдаа гарлаа</h1>
        <p className="max-w-sm text-base text-ink-soft">
          Хуудсыг ачаалахад алдаа гарлаа. Систем шинэчлэгдсэн байж магадгүй — дахин ачаална уу. Таны
          хадгалсан мэдээлэл устахгүй.
        </p>
        <button
          type="button"
          className="min-h-12 rounded-xl bg-action px-6 text-lg font-bold text-white"
          onClick={() => window.location.reload()}
        >
          Дахин ачаалах
        </button>
        <button type="button" className="text-sm font-semibold text-action" onClick={() => window.location.assign("/")}>
          Нүүр хуудас руу
        </button>
      </div>
    );
  }
}
