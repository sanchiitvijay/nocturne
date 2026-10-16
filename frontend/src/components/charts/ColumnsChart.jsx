import { LuClock } from "react-icons/lu";
import { useElementWidth } from "../../hooks/useElementWidth";
import { compact, date, num } from "../../lib/format";
import EmptyState from "../ui/EmptyState";
import { TipRow, useTooltip } from "../ui/Tooltip";
import { axisText, barPath, baseLine, gridLine, niceMax } from "./scale";

/** Single-series columns (events per day) with the critical share drawn on top. */
export default function ColumnsChart({ rows, height = 160, x = (r) => r.day, y = (r) => r.n, accent = (r) => r.p1 }) {
  const [ref, width] = useElementWidth(520);
  const tip = useTooltip();
  if (!rows?.length) return <EmptyState icon={LuClock} title="No dated events" />;

  const W = Math.max(width, 280), H = height, m = { l: 36, r: 6, t: 8, b: 22 };
  const yMax = niceMax(Math.max(...rows.map(y), 1)), iw = W - m.l - m.r, ih = H - m.t - m.b;
  const band = iw / rows.length, bw = Math.max(2, Math.min(18, band * 0.7));
  const Y = (v) => m.t + ih - (v / yMax) * ih;
  const every = Math.ceil(rows.length / Math.max(2, Math.floor(iw / 64)));

  return (
    <div ref={ref} className="w-full">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block max-w-full">
        {[0, yMax / 2, yMax].map((v) => (
          <g key={v}>
            <line x1={m.l} x2={W - m.r} y1={Y(v)} y2={Y(v)} style={gridLine} />
            <text x={m.l - 6} y={Y(v) + 4} textAnchor="end" style={axisText}>{compact(v)}</text>
          </g>
        ))}
        {rows.map((r, i) => {
          const xx = m.l + i * band + (band - bw) / 2, v = y(r), a = accent(r) || 0;
          return (
            <g key={x(r) ?? i}>
              {v > 0 && <path d={barPath(xx, Y(v), bw, Y(0) - Y(v))} style={{ fill: "var(--brand-200)" }} />}
              {a > 0 && <path d={`M${xx},${Y(a)}h${bw}v${Y(0) - Y(a)}h${-bw}Z`} style={{ fill: "var(--p1)" }} />}
              {i % every === 0 && <text x={xx + bw / 2} y={H - 6} textAnchor="middle" style={axisText}>{date(x(r))}</text>}
              <rect x={m.l + i * band} y={m.t} width={band} height={ih} fill="transparent"
                onMouseMove={(e) => tip.show(e, (
                  <>
                    <b className="mb-1 block">{date(x(r))}</b>
                    <TipRow label="Events" value={num(v)} />
                    <TipRow label="Critical" value={num(a)} color="var(--p1)" />
                  </>
                ))}
                onMouseLeave={tip.hide} />
            </g>
          );
        })}
        <line x1={m.l} x2={W - m.r} y1={Y(0)} y2={Y(0)} style={baseLine} />
      </svg>
      {tip.node}
    </div>
  );
}
