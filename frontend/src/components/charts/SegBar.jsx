import { num } from "../../lib/format";

/** One bar split into coloured parts with a legend. parts: [{label, value, color}] */
export default function SegBar({ parts }) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-surface-3">
        {parts.filter((p) => p.value).map((p) => (
          <i key={p.label} style={{ flexGrow: p.value, background: p.color }} title={`${p.label}: ${num(p.value)}`} />
        ))}
      </div>
      <Legend items={parts.map((p) => ({ ...p, extra: `${Math.round((100 * p.value) / total)}%` }))} />
    </div>
  );
}

/** Colour key. items: [{label, color, value?, extra?, round?}] */
export function Legend({ items, note }) {
  return (
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-2">
      {items.map((p) => (
        <span key={p.label} className="inline-flex items-center gap-1.5">
          <i className={`size-2.5 ${p.round ? "rounded-full" : "rounded-sm"}`} style={{ background: p.color }} />
          {p.label}{p.value !== undefined && <b className="text-ink">{typeof p.value === "number" ? num(p.value) : p.value}</b>}
          {p.extra && <span className="text-ink-3">{p.extra}</span>}
        </span>
      ))}
      {note && <span className="text-ink-3">{note}</span>}
    </div>
  );
}
