import { num } from "../../lib/format";
import { TipRow, useTooltip } from "../ui/Tooltip";

// US states on a 12 × 8 grid: [column, row].
const TILES = {
  AK: [0, 0], ME: [11, 0], VT: [10, 1], NH: [11, 1], WA: [1, 2], ID: [2, 2], MT: [3, 2], ND: [4, 2], MN: [5, 2], IL: [6, 2], WI: [7, 2],
  MI: [8, 2], NY: [9, 2], RI: [10, 2], MA: [11, 2], OR: [1, 3], NV: [2, 3], WY: [3, 3], SD: [4, 3], IA: [5, 3], IN: [6, 3], OH: [7, 3],
  PA: [8, 3], NJ: [9, 3], CT: [10, 3], CA: [1, 4], UT: [2, 4], CO: [3, 4], NE: [4, 4], MO: [5, 4], KY: [6, 4], WV: [7, 4], VA: [8, 4],
  MD: [9, 4], DE: [10, 4], AZ: [2, 5], NM: [3, 5], KS: [4, 5], AR: [5, 5], TN: [6, 5], NC: [7, 5], SC: [8, 5], DC: [9, 5], OK: [4, 6],
  LA: [5, 6], MS: [6, 6], AL: [7, 6], GA: [8, 6], HI: [0, 7], TX: [4, 7], FL: [9, 7],
};
const COLS = 12, ROWS = 8;

/** Tile map of US states shaded by `metric`. `selected` outlines one state; `onPick(state)` makes tiles clickable. */
export default function Tilegram({ states, metric = "n", label = "alerts", onPick, selected }) {
  const tip = useTooltip();
  const by = Object.fromEntries((states || []).map((s) => [s.state, s]));
  const max = Math.max(...(states || []).map((s) => s[metric] || 0), 1);
  const cells = Array.from({ length: COLS * ROWS }, () => null);
  Object.entries(TILES).forEach(([st, [c, r]]) => { cells[r * COLS + c] = st; });

  return (
    <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))` }}>
      {cells.map((st, i) => {
        if (!st) return <div key={i} />;
        const d = by[st], v = d ? d[metric] || 0 : 0;
        const step = v ? 1 + Math.min(5, Math.floor(Math.sqrt(v / max) * 6)) : 0;
        const clickable = onPick && d;
        return (
          <button key={st} type="button" disabled={!clickable}
            onClick={clickable ? () => onPick(st) : undefined}
            onMouseMove={d ? (e) => tip.show(e, (
              <>
                <b className="mb-1 block">{st}</b>
                <TipRow label={`Actionable ${label}`} value={num(d[metric] || 0)} />
                <TipRow label="Critical" value={num(d.p1 || 0)} />
                <TipRow label="Sites" value={num(d.sites || 0)} />
              </>
            )) : undefined}
            onMouseLeave={tip.hide}
            className={`aspect-square rounded-[5px] text-[10px] font-bold transition-transform disabled:cursor-default ${clickable ? "hover:scale-110" : ""} ${
              selected === st ? "ring-2 ring-p2 ring-offset-1 ring-offset-surface" : ""}`}
            style={{ background: step ? `var(--seq-${step})` : "var(--surface-3)", color: step >= 4 ? "#fff" : step ? "var(--brand-700)" : "var(--text-3)" }}>
            {st}
          </button>
        );
      })}
      {tip.node}
    </div>
  );
}
