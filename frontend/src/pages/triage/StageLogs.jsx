import { Link } from "react-router-dom";
import { LuClock, LuMapPin, LuRefreshCw } from "react-icons/lu";
import Fact from "../../components/ui/Fact";
import SeverityBadge from "../../components/ui/SeverityBadge";
import Signal from "../../components/ui/Signal";
import { roleIcon } from "../../lib/icons";
import { sevColor } from "../../lib/domain";
import { date, dur, num, stamp, time } from "../../lib/format";

function Outage({ a, e }) {
  const o = a.outage;
  if (o) {
    return o.minutes != null
      ? <Signal tone="good"><b>Recovered after {dur(o.minutes)}</b><br /><span className="opacity-80">Down {time(o.down_ts)}, back {time(o.up_ts)} ({date(o.up_ts)})</span></Signal>
      : <Signal tone="critical"><b>No recovery event yet</b><br /><span className="opacity-80">Down since {stamp(o.down_ts)}</span></Signal>;
  }
  if (!e.transition) return null;
  return <Signal>No matching {e.transition === "down" ? "recovery" : "outage"} found for this {e.transition === "down" ? "drop" : "recovery"}.</Signal>;
}

export default function StageLogs({ analysis: a, event: e }) {
  const rec = a.recurrence || {};
  const blastDevices = new Set(a.blast_radius.map((b) => b.device_id)).size;
  return (
    <div className="flex flex-col gap-3">
      <Outage a={a} e={e} />
      {a.flap_cycles >= 3
        ? <Signal tone="warning"><b>Flapping</b>: {a.flap_cycles} short down/up cycles in the last week.</Signal>
        : a.flap_cycles > 0 && <Signal>{a.flap_cycles} short down/up cycle{a.flap_cycles > 1 ? "s" : ""} in the last week.</Signal>}
      {a.blast_radius.length > 0 && (
        <Signal tone="critical">
          <b>{blastDevices} other device(s) at this site dropped within ±15 min</b>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {a.blast_radius.slice(0, 12).map((b) => {
              const Icon = roleIcon(b.role);
              return (
                <Link key={b.id} to={`/alerts/${b.id}`} className="inline-flex items-center gap-1 rounded-md bg-surface px-2 py-0.5 font-mono text-xs text-p1-ink">
                  <Icon className="size-3.5" />{b.device_name} {time(b.ts)}
                </Link>
              );
            })}
          </div>
        </Signal>
      )}
      {rec.same_type_device !== undefined && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <Fact icon={LuRefreshCw}>{num(rec.same_type_device)}× on this device in 7 days</Fact>
          <Fact icon={LuMapPin}>{num(rec.same_type_site)}× at this site</Fact>
          {a.mttr_device != null && <Fact icon={LuClock}>Device median recovery {dur(a.mttr_device)}</Fact>}
        </div>
      )}
      <div>
        <h4 className="mb-2 text-sm">Device timeline (±24 h)</h4>
        {a.timeline.length ? (
          <div className="max-h-[420px] overflow-y-auto rounded-xl border border-line">
            {a.timeline.map((t) => (
              <Link key={t.id} to={`/alerts/${t.id}`}
                className={`grid grid-cols-[70px_1fr_auto] items-start gap-3 border-b border-line px-3 py-2 text-ink last:border-0 hover:bg-hover hover:no-underline ${t.id === e.id ? "bg-brand-50" : ""}`}>
                <span className="text-[11.5px] tabular-nums text-ink-3">{time(t.ts)}<br />{date(t.ts)}</span>
                <span className="min-w-0 border-l-2 pl-3 text-[13px]" style={{ borderColor: sevColor(t.severity) }}>
                  {t.transition === "down" ? "↓ " : t.transition === "up" ? "↑ " : ""}{t.name}
                  <br /><span className="text-xs text-ink-3">{(t.message || "").slice(0, 80)}</span>
                </span>
                <SeverityBadge severity={t.severity} short />
              </Link>
            ))}
          </div>
        ) : <p className="text-sm text-ink-3">No other events for this device within ±24 hours.</p>}
      </div>
    </div>
  );
}
