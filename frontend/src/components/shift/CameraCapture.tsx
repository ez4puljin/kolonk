/**
 * Аппын дотоод камер — милийн зургийг ЗӨВХӨН одоо дарж авахад.
 *
 * Галерей нээгддэггүй (getUserMedia-ийн шууд урсгал), дарсан кадр дээр
 * огноо/цаг, салбар, түгээгчийн нэр тамгалагдаж JPEG болно. Камер нээгдэхгүй
 * бол (зөвшөөрөл өгөөгүй, HTTP) `onUnavailable` дуудагдаж эцэг нь
 * `<input capture>` руу буцна.
 */
import { useEffect, useRef, useState } from "react";
import { Camera, RefreshCw } from "lucide-react";

import { t } from "../../i18n/mn";
import { stampImage } from "../../lib/photo";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

export function CameraCapture({
  open,
  title,
  stampLines,
  onCapture,
  onClose,
  onUnavailable,
}: {
  open: boolean;
  title: string;
  /** Дарах мөчид тооцоолно — цаг яг дарсан секундээр бичигдэнэ. */
  stampLines: () => string[];
  onCapture: (file: File) => void;
  onClose: () => void;
  onUnavailable: (reason: string) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ file: File; url: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setReady(false);
    setPreview(null);
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          void video.play().catch(() => undefined);
        }
        setReady(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        onUnavailable(error instanceof Error ? error.message : String(error));
      });
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };
    // onUnavailable нь inline функц — камерыг зөвхөн нээх/хаахад асаана.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview.url);
  }, [preview]);

  const shoot = async (): Promise<void> => {
    const video = videoRef.current;
    if (!video || busy) return;
    setBusy(true);
    try {
      const file = await stampImage(video, stampLines());
      setPreview({ file, url: URL.createObjectURL(file) });
    } catch (error: unknown) {
      onUnavailable(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} size="md" title={title}>
      <div className="flex flex-col gap-3">
        <div className="relative overflow-hidden rounded-xl bg-black" style={{ aspectRatio: "4 / 3" }}>
          {preview ? (
            <img src={preview.url} alt="" className="h-full w-full object-contain" />
          ) : (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-cover"
            />
          )}
          {!ready && !preview ? (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-white/80">
              {t.attendant.cameraStarting}
            </div>
          ) : null}
        </div>
        <p className="text-xs text-ink-soft">{t.attendant.cameraHint}</p>
        {preview ? (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="lg"
              icon={<RefreshCw />}
              onClick={() => setPreview(null)}
              className="flex-1"
            >
              {t.attendant.retake}
            </Button>
            <Button
              variant="success"
              size="lg"
              onClick={() => {
                onCapture(preview.file);
                onClose();
              }}
              className="flex-1"
            >
              {t.attendant.usePhoto}
            </Button>
          </div>
        ) : (
          <Button
            variant="primary"
            size="lg"
            block
            icon={<Camera />}
            disabled={!ready}
            loading={busy}
            onClick={() => void shoot()}
          >
            {t.attendant.shoot}
          </Button>
        )}
      </div>
    </Modal>
  );
}
