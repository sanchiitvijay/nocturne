import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuList } from "react-icons/lu";
import { compact } from "../../lib/format";
import EmptyState from "../ui/EmptyState";

/**
 * Ranked horizontal bars. `href(item)` makes rows links; `alt(item)` overlays a darker share (e.g. actionable).
 */
export default function HBars({ items, label = (d) => d.name, value = (d) => d.n, href, sub, alt, getKey = (d, i) => i }) {
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(t);
  }, []);
  if (!items?.length) return <EmptyState icon={LuList} title="Nothing to rank yet" text="Data appears once alerts are imported or simulated." />;
  const max = Math.max(...items.map(value), 1);
  return (
    <div className="flex flex-col gap-1">
      {items.map((d, i) => {
        const inner = (
          <>
            <span className="min-w-0 text-[13px]">
              <span className="block truncate font-medium" title={label(d)}>{label(d)}</span>
              {sub && <small className="block truncate text-xs text-ink-3">{sub(d)}</small>}
            </span>
            <span className="relative h-2.5 overflow-hidden rounded-full bg-surface-3">
              <i className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700" style={{ width: grown ? `${(100 * value(d)) / max}%` : 0, background: alt ? "var(--brand-200)" : "var(--brand)" }} />
              {alt && <i className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700" style={{ width: grown ? `${(100 * alt(d)) / max}%` : 0, background: "var(--brand)" }} />}
            </span>
            <span className="text-right text-[13px] font-semibold tabular-nums">{compact(value(d))}</span>
          </>
        );
        const cls = "grid grid-cols-[minmax(0,1.1fr)_minmax(60px,1fr)_auto] items-center gap-3 rounded-lg px-2 py-1.5 text-ink";
        return href
          ? <Link key={getKey(d, i)} to={href(d)} className={`${cls} hover:bg-hover hover:no-underline`}>{inner}</Link>
          : <div key={getKey(d, i)} className={cls}>{inner}</div>;
      })}
    </div>
  );
}
