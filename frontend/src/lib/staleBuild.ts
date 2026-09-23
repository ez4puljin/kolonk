/**
 * Шинэ хувилбар гарсны дараах «хуучин таб» асуудал.
 *
 * Deploy хийхэд JS файлуудын нэр (hash) солигддог. Хуучин хувилбар ачаалсан
 * таб (iPhone Safari табаа хаалгүй удаан хадгалдаг) дараагийн хуудас руу
 * шилжихэд хуучин нэртэй файлыг татах гэж 404 авч, програм бүхэлдээ хар
 * дэлгэц болдог байв. Ийм үед хуудсыг НЭГ удаа дахин ачаалж шинэ хувилбарыг
 * авна; 30 секундын дотор дахин тохиолдвол давталт үүсгэхгүйн тулд зогсоно.
 */
const KEY = "kolonk-stale-reload-at";

export function isChunkLoadError(error: unknown): boolean {
  const text = String((error as { message?: string } | null)?.message ?? error ?? "");
  return /dynamically imported module|Importing a module script failed|Failed to fetch|error loading dynamically|ChunkLoadError|Unable to preload CSS/i.test(
    text,
  );
}

/** Дахин ачаалсан бол true (дуудагч цаашид юу ч хийх шаардлагагүй). */
export function reloadForNewVersion(): boolean {
  try {
    const last = Number(sessionStorage.getItem(KEY) ?? "0");
    if (Date.now() - last < 30_000) return false;
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    // sessionStorage хаалттай (хувийн горим) — нэг удаа л оролдоно.
  }
  window.location.reload();
  return true;
}
