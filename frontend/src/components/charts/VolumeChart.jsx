import { LuActivity } from "react-icons/lu";
import { useLabels } from "../../context/AuthContext";
import { useElementWidth } from "../../hooks/useElementWidth";
import { sevColor } from "../../lib/domain";
import { compact, date, hhmm, num, stamp } from "../../lib/format";
import EmptyState from "../ui/EmptyState";
import { TipRow, useTooltip } from "../ui/Tooltip";
import { axisText, barPath, baseLine, gridLine, niceMax } from "./scale";
import { useSeverityKeys } from "./useSeverityKeys";

/** Columns over time, stacked by severity. `bucket` is "hour" or "day". */
export default function VolumeChart({ rows, bucket }) {
  const [ref, width] = useElementWidth(640);
  const tip = useTooltip();
  const labels = useLabels();
  const sevs = useSeverityKeys();
  if (!rows?.length) return <EmptyState icon={LuActivity} title="No events in this window" text="Choose a wider window or import data in Data Studio." />;

  const W = Math.max(width, 320), H = 230, m = { l: 44, r: 8, t: 10, b: 26 };
  const totals = rows.map((r) => sevs.reduce((a, k) => a + (r[k] || 0), 0));
  const yMax = niceMax(Math.max(...totals, 1)), iw = W - m.l - m.r, ih = H - m.t - m.b;
  const band = iw / rows.length, bw = Math.max(2, Math.min(24, band * 0.72));
  const y = (v) => m.t + ih - (v / yMax) * ih;
  const every = Math.ceil(rows.length / Math.max(2, Math.floor(iw / 70)));
  const tickLabel = (t) => (bucket === "hour" ? (hhmm(t) === "00:00" ? date(t) : hhmm(t)) : date(t));

  return (
    <div ref={ref} className="w-full">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block max-w-full">
        {[0, 1, 2, 3, 4].map((i) => {
          const v = (yMax / 4) * i;
          return (
            <g key={i}>
              <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} style={gridLine} />
              <text x={m.l - 8} y={y(v) + 4} textAnchor="end" style={axisText}>{compact(v)}</text>
            </g>
          );
        })}
        {rows.map((r, i) => {
          const x = m.l + i * band + (band - bw) / 2;
          let acc = 0;
          const present = sevs.filter((k) => r[k] > 0);
          return (
            <g key={r.t}>
              {present.map((k, si) => {
                const v = r[k];
                const y0 = y(acc), y1 = y(acc + v);
                acc += v;
                const top = si === present.length - 1;
                const h = Math.max(y0 - y1 - (si > 0 ? 2 : 0), 1);
                return <path key={k} d={top ? barPath(x, y1, bw, h) : `M${x},${y1}h${bw}v${h}h${-bw}Z`} style={{ fill: sevColor(k) }} />;
              })}
              {i % every === 0 && <text x={x + bw / 2} y={H - 8} textAnchor="middle" style={axisText}>{tickLabel(r.t)}</text>}
              <rect x={m.l + i * band} y={m.t} width={band} height={ih} fill="transparent"
                onMouseMove={(e) => tip.show(e, (
                  <>
                    <b className="mb-1 block">{bucket === "hour" ? stamp(`${r.t}:00`) : date(r.t)}</b>
                    {sevs.map((k) => <TipRow key={k} color={sevColor(k)} label={`${k} ${labels.severity(k)}`} value={num(r[k] || 0)} />)}
                    <TipRow label="Total" value={num(totals[i])} />
                  </>
                ))}
                onMouseLeave={tip.hide} />
            </g>
          );
        })}
        <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} style={baseLine} />
      </svg>
      {tip.node}
    </div>
  );
}
