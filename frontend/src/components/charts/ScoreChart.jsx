import { LuActivity } from "react-icons/lu";
import { useLabels } from "../../context/AuthContext";
import { useElementWidth } from "../../hooks/useElementWidth";
import { sevColor } from "../../lib/domain";
import { cap, num, pad2 } from "../../lib/format";
import EmptyState from "../ui/EmptyState";
import { TipRow, useTooltip } from "../ui/Tooltip";

/**
 * Hour of day (x) × category (row). Dot size = actionable alerts, colour = worst severity in that hour.
 * `onPick(category, hour)` makes the dots clickable.
 */
export default function ScoreChart({ rows, onPick }) {
  const [ref, width] = useElementWidth(720);
  const tip = useTooltip();
  const labels = useLabels();
  if (!rows?.length) return <EmptyState icon={LuActivity} title="Nothing actionable in this window" text="Actionable alerts appear here by hour of day." />;

  const W = Math.max(width, 560), rowH = 38, m = { l: 112, r: 16, t: 26, b: 10 }, H = m.t + rows.length * rowH + m.b;
  const iw = W - m.l - m.r, col = iw / 24;
  const max = Math.max(...rows.flatMap((r) => r.hours.map((h) => h.n)), 1);

  return (
    <div ref={ref} className="w-full overflow-x-auto">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block">
        {Array.from({ length: 8 }, (_, i) => i * 3).map((h) => (
          <text key={h} x={m.l + h * col + col / 2} y={14} textAnchor="middle" style={{ fill: "var(--text-3)", fontSize: 11 }}>{pad2(h)}:00</text>
        ))}
        {rows.map((r, i) => {
          const cy = m.t + i * rowH + rowH / 2;
          return (
            <g key={r.category}>
              <line x1={m.l - 6} x2={W - m.r} y1={cy} y2={cy} style={{ stroke: "var(--border)" }} />
              <text x={0} y={cy + 4} style={{ fill: "var(--text-2)", fontSize: 12.5, fontWeight: 600 }}>{cap(r.category)}</text>
              {r.hours.filter((h) => h.n).map((h) => {
                const rad = 3.5 + Math.sqrt(h.n / max) * (Math.min(col, rowH) / 2 - 3);
                return (
                  <circle key={h.h} cx={m.l + h.h * col + col / 2} cy={cy} r={rad.toFixed(1)}
                    style={{ fill: sevColor(h.worst), cursor: onPick ? "pointer" : "default", opacity: 0.9 }}
                    onClick={onPick ? () => onPick(r.category, h.h) : undefined}
                    onMouseMove={(e) => tip.show(e, (
                      <>
                        <b className="mb-1 block">{cap(r.category)} at {pad2(h.h)}:00–{pad2(h.h)}:59</b>
                        <TipRow label="Actionable alerts" value={num(h.n)} />
                        <TipRow label="Worst severity" value={`${h.worst} ${labels.severity(h.worst)}`} color={sevColor(h.worst)} />
                      </>
                    ))}
                    onMouseLeave={tip.hide} />
                );
              })}
            </g>
          );
        })}
      </svg>
      {tip.node}
    </div>
  );
}
