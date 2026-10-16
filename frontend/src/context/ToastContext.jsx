import { createContext, useCallback, useContext, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuCircleAlert, LuCircleCheck, LuInfo, LuSiren, LuX } from "react-icons/lu";

const ToastCtx = createContext(() => {});
const MAX = 4;
const TONES = {
  ok: { cls: "border-good/40", icon: LuCircleCheck, iconCls: "text-good" },
  error: { cls: "border-p1/40", icon: LuCircleAlert, iconCls: "text-p1" },
  alert: { cls: "border-p1/60", icon: LuSiren, iconCls: "text-p1" },
  info: { cls: "border-line", icon: LuInfo, iconCls: "text-brand" },
};

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setItems((xs) => xs.filter((t) => t.id !== id)), []);
  const toast = useCallback((message, tone = "info", { link, ms = 5200 } = {}) => {
    const id = nextId.current++;
    setItems((xs) => [...xs, { id, message, tone, link }].slice(-MAX));
    setTimeout(() => dismiss(id), ms);
  }, [dismiss]);

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {items.map((t) => {
          const tone = TONES[t.tone] || TONES.info;
          const Icon = tone.icon;
          return (
            <div key={t.id} className={`pointer-events-auto flex animate-rise items-start gap-3 rounded-xl border bg-surface p-3 pr-2 text-sm shadow-pop ${tone.cls}`}>
              <Icon className={`mt-0.5 size-5 flex-none ${tone.iconCls}`} aria-hidden />
              <div className="min-w-0 flex-1">
                {t.message}
                {t.link && (
                  <> <Link to={t.link.to} className="font-semibold" onClick={() => dismiss(t.id)}>{t.link.text}</Link></>
                )}
              </div>
              <button type="button" onClick={() => dismiss(t.id)} className="rounded-md p-1 text-ink-3 hover:bg-hover" aria-label="Dismiss">
                <LuX className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

 
export const useToast = () => useContext(ToastCtx);
