import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { LuX } from "react-icons/lu";

/** Dialog rendered over a scrim. Closes on Escape and on a click outside. */
export default function Modal({ open, onClose, title, children, footer, width = "max-w-lg" }) {
  const box = useRef(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") closeRef.current(); };
    document.addEventListener("keydown", onKey);
    const t = setTimeout(() => box.current?.querySelector("input,textarea,select,button:not([data-close])")?.focus(), 30);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); clearTimeout(t); document.body.style.overflow = prev; };
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[70] grid place-items-center overflow-y-auto bg-[#03121c]/55 p-4 backdrop-blur-[2px]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={box} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}
        className={`w-full ${width} animate-rise rounded-2xl border border-line bg-surface p-5 shadow-pop sm:p-6`}>
        <div className="mb-3 flex items-start gap-3">
          <h2 className="flex-1 text-lg">{title}</h2>
          <button type="button" data-close onClick={onClose} className="rounded-lg p-1.5 text-ink-3 hover:bg-hover" aria-label="Close">
            <LuX className="size-5" />
          </button>
        </div>
        {children}
        {footer && <div className="mt-5 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
