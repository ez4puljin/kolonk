/**
 * Ээлжийн зургийн туслахууд — камераар авсан зураг дээр огноо/цаг тамгалах,
 * хэт том зургийг багасгах, галерейгээс сонгосон хуучин зургийг таних.
 */

/** Зургийн урт талын дээд хэмжээ (px) — 10MB-ийн хязгаарт багтааж, дата хэмнэнэ. */
const MAX_SIDE = 1600;

/** Камераар «сая» дарсан гэж үзэх хамгийн урт хугацаа (мс). */
const FRESH_MS = 3 * 60_000;

/** Аппын камер ажиллах боломжтой юу (HTTPS/localhost + getUserMedia). */
export function cameraAvailable(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof window !== "undefined" &&
    window.isSecureContext === true &&
    typeof navigator.mediaDevices?.getUserMedia === "function"
  );
}

/**
 * Файлын систем дээрх зураг «сая» дарагдсан уу — галерейгаас хуучин зураг
 * сонгосныг таних сүүлийн хамгаалалт (`capture` атрибутыг зарим утас үл тоодог).
 */
export function isFreshCapture(file: File, maxAgeMs: number = FRESH_MS): boolean {
  if (!file.lastModified) return true;
  const age = Date.now() - file.lastModified;
  // Утасны цаг урагш/хойш зөрж болох тул сөрөг утгыг ч шинэ гэж үзнэ.
  return age <= maxAgeMs;
}

type Source = HTMLVideoElement | HTMLCanvasElement | HTMLImageElement | ImageBitmap;

function sourceSize(source: Source): { width: number; height: number } {
  if (source instanceof HTMLVideoElement) {
    return { width: source.videoWidth, height: source.videoHeight };
  }
  if (source instanceof HTMLImageElement) {
    return { width: source.naturalWidth, height: source.naturalHeight };
  }
  return { width: source.width, height: source.height };
}

/**
 * Эх зургийг (видеоны кадр, файл) canvas дээр буулгаж, доод буланд нь
 * тамганы мөрүүдийг (огноо/цаг, салбар, түгээгч) бичээд JPEG файл буцаана.
 */
export async function stampImage(
  source: Source,
  lines: string[],
  fileName: string = `mile-${Date.now()}.jpg`,
): Promise<File> {
  const { width, height } = sourceSize(source);
  if (width === 0 || height === 0) throw new Error("Зураг хоосон байна");
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas ажиллахгүй байна");
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);

  // Тамга — зургийн хэмжээнд пропорциональ, хар хагас тунгалаг дэвсгэртэй.
  const fontPx = Math.max(16, Math.round(canvas.width / 32));
  const pad = Math.round(fontPx * 0.6);
  const lineH = Math.round(fontPx * 1.3);
  ctx.font = `bold ${fontPx}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
  const textW = Math.max(...lines.map((line) => ctx.measureText(line).width), 0);
  const boxW = textW + pad * 2;
  const boxH = lineH * lines.length + pad * 2 - (lineH - fontPx);
  const x = canvas.width - boxW - pad;
  const y = canvas.height - boxH - pad;
  ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
  ctx.fillRect(x, y, boxW, boxH);
  ctx.fillStyle = "#ffdd57";
  ctx.textBaseline = "top";
  lines.forEach((line, index) => {
    ctx.fillText(line, x + pad, y + pad + index * lineH);
  });

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.88),
  );
  if (!blob) throw new Error("Зураг хадгалж чадсангүй");
  return new File([blob], fileName, { type: "image/jpeg", lastModified: Date.now() });
}

/** Файлаас зураг ачаалж (EXIF эргүүлэлтийг хөтөч өөрөө тооцно) тамгална. */
export async function stampFile(file: File, lines: string[]): Promise<File> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    try {
      return await stampImage(bitmap, lines, file.name.replace(/\.[^.]+$/, "") + "-stamped.jpg");
    } finally {
      bitmap.close();
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Зураг уншиж чадсангүй"));
      img.src = url;
    });
    return await stampImage(image, lines, file.name.replace(/\.[^.]+$/, "") + "-stamped.jpg");
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Тамганы огноо/цаг: 2026-09-13 14:05:33 (станцын локал цаг). */
export function stampClock(date: Date = new Date()): string {
  const p = (n: number): string => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())} ${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
}
