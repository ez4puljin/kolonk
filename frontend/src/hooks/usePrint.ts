import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * React зангилааг нуугдмал `iframe`-д зурж хэвлэнэ (80мм баримт, тайлан).
 *
 * Хэрэглээ: `const { print, portal } = usePrint();` — `portal`-ыг компонентын
 * буцаалтад заавал зурна, `print(<Receipt .../>)` дуудахад хэвлэх цонх нээгдэнэ.
 */
export function usePrint(): { print: (content: ReactNode) => void; portal: ReactNode; printing: boolean } {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [content, setContent] = useState<ReactNode>(null);

  const teardown = useCallback(() => {
    setContent(null);
    setTarget(null);
    const frame = frameRef.current;
    frameRef.current = null;
    if (frame && frame.parentNode) frame.parentNode.removeChild(frame);
  }, []);

  const print = useCallback(
    (node: ReactNode) => {
      // Өмнөх хэвлэлтийн frame үлдсэн бол цэвэрлэнэ.
      if (frameRef.current?.parentNode) frameRef.current.parentNode.removeChild(frameRef.current);

      const frame = document.createElement("iframe");
      frame.setAttribute("aria-hidden", "true");
      frame.style.position = "fixed";
      frame.style.right = "0";
      frame.style.bottom = "0";
      frame.style.width = "0";
      frame.style.height = "0";
      frame.style.border = "0";
      frame.style.visibility = "hidden";
      document.body.appendChild(frame);
      frameRef.current = frame;

      const doc = frame.contentDocument;
      if (!doc) {
        teardown();
        return;
      }

      doc.open();
      doc.write('<!doctype html><html lang="mn"><head><meta charset="utf-8"></head><body></body></html>');
      doc.close();

      // Хуудасны хэв маягийг frame рүү хуулна (Vite dev = <style>, prod = <link>).
      const styleNodes = Array.from(document.head.querySelectorAll('style, link[rel="stylesheet"]'));
      for (const styleNode of styleNodes) doc.head.appendChild(styleNode.cloneNode(true));

      const base = doc.createElement("style");
      base.textContent =
        "html,body{margin:0;padding:0;background:#fff;color:#000;}" +
        ".no-print{display:none!important;}.print-only{display:block!important;}";
      doc.head.appendChild(base);

      setTarget(doc.body);
      setContent(node);
    },
    [teardown],
  );

  useEffect(() => {
    if (!target || content === null) return;
    const frame = frameRef.current;
    if (!frame) return;

    // Хэв маяг ачаалагдах богино хугацаа өгнө.
    const timer = window.setTimeout(() => {
      try {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
      } finally {
        window.setTimeout(teardown, 500);
      }
    }, 250);

    return () => window.clearTimeout(timer);
  }, [target, content, teardown]);

  useEffect(() => teardown, [teardown]);

  const portal = target && content !== null ? createPortal(content, target) : null;

  return { print, portal, printing: content !== null };
}
