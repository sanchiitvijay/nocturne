import { pad2 } from "../../lib/format";

/** 24 small columns: events per hour of day, with one hour highlighted. */
export default function HourProfile({ values, highlight = -1 }) {
  const max = Math.max(...values, 1);
  return (
    <div>
      <div className="flex h-12 items-end gap-0.5">
        {values.map((v, h) => (
          <i key={h} title={`${pad2(h)}:00 ${v} events`} className="flex-1 rounded-t-[3px]"
            style={{ height: Math.max(2, (48 * v) / max), background: h === highlight ? "var(--p1)" : "var(--brand-200)" }} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-ink-3"><span>00:00</span><span>12:00</span><span>23:00</span></div>
    </div>
  );
}
