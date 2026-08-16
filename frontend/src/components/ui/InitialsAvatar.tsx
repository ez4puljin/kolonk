/** erxes-маягийн дугуй товчлол — нэрний эхний үсгүүд, id-ээс тогтмол өнгөтэй. */

const TONES = [
  "bg-teal-100 text-teal-700",
  "bg-sky-100 text-sky-700",
  "bg-violet-100 text-violet-700",
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-emerald-100 text-emerald-700",
] as const;

export interface InitialsAvatarProps {
  /** Товчлол авах нэр(с) — эхний 2 үгийн эхний үсгүүд. */
  name: string;
  /** Өнгө сонгох тогтмол үр (ихэвчлэн бичлэгийн id). */
  seed: string;
  size?: "md" | "lg";
}

export function InitialsAvatar({ name, seed, size = "md" }: InitialsAvatarProps) {
  const words = name.trim().split(/\s+/);
  const initials = (
    (words[0]?.[0] ?? "") + (words[1]?.[0] ?? words[0]?.[1] ?? "")
  ).toUpperCase() || "?";
  let hash = 0;
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const tone = TONES[hash % TONES.length];
  const dims = size === "lg" ? "h-11 w-11 text-[15px]" : "h-9 w-9 text-[13px]";
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full font-bold ${dims} ${tone}`}>
      {initials}
    </span>
  );
}

export default InitialsAvatar;
