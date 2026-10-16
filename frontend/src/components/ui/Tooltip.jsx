import { useCallback, useState } from "react";
import { createPortal } from "react-dom";

/** Mouse-following tooltip for charts: const tip = useTooltip(); onMouseMove={(e) => tip.show(e, content)} */
 
export function useTooltip() {
  const [tip, setTip] = useState(null);
  const show = useCallback((e, content) => setTip({ x: e.clientX, y: e.clientY, content }), []);
  const hide = useCallback(() => setTip(null), []);
  const node = tip ? createPortal(<TooltipBox {...tip} />, document.body) : null;
  return { show, hide, node };
}

function TooltipBox({ x, y, content }) {
  const w = 240, left = x + 14 + w > window.innerWidth ? x - w - 14 : x + 14;
  const top = y + 14 + 140 > window.innerHeight ? y - 140 : y + 14;
  return (
    <div role="tooltip" className="pointer-events-none fixed z-[95] max-w-[240px] rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-pop" style={{ left, top }}>
      {content}
    </div>
  );
}

/** One "label …… value" line inside a tooltip. */
export function TipRow({ label, value, color }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="flex items-center gap-1.5 text-ink-2">{color && <i className="size-2 rounded-sm" style={{ background: color }} />}{label}</span>
      <b className="tabular-nums">{value}</b>
    </div>
  );
}
