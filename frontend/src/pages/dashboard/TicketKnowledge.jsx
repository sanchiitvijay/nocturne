import Kind from "../../components/ui/Kind";
import Meter from "../../components/ui/Meter";
import { StatGrid, StatTile } from "../../components/ui/StatTile";
import { kindColor } from "../../lib/domain";
import { dur, num, pct } from "../../lib/format";

export default function TicketKnowledge({ tickets: t = {} }) {
  return (
    <div>
      <StatGrid>
        <StatTile value={num(t.total || 0)} label="Tickets imported" />
        <StatTile value={num(t.open || 0)} label="Still open" />
        <StatTile value={`${pct(t.linked, t.total)}%`} label="Linked to devices or sites" />
        <StatTile value={dur(t.avg_resolve)} label="Average time to close" />
      </StatGrid>
      <div className="mt-4 flex flex-col gap-2.5">
        {(t.kinds || []).map((k) => (
          <div key={k.kind} className="flex items-center gap-3">
            <span className="w-12"><Kind kind={k.kind} /></span>
            <Meter className="flex-1" value={(100 * k.n) / (t.total || 1)} color={kindColor(k.kind)} />
            <span className="min-w-[110px] text-right text-[13px] tabular-nums">{num(k.n)} <span className="text-ink-3">({num(k.open)} open)</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}
