import { Link } from "react-router-dom";
import { LuChevronRight } from "react-icons/lu";
import HourProfile from "../../components/charts/HourProfile";
import HealthRing from "../../components/ui/HealthRing";
import KeyValue from "../../components/ui/KeyValue";
import Signal from "../../components/ui/Signal";
import { Skeleton } from "../../components/ui/Skeleton";
import { roleLabel } from "../../lib/domain";
import { roleIcon } from "../../lib/icons";
import { num, stamp } from "../../lib/format";
import { useSeverityKeys } from "../../components/charts/useSeverityKeys";

const HIDDEN_EXTRA = ["scenario", "by"];

function Health({ analysis, event }) {
  const sevs = useSeverityKeys();
  if (!analysis) return <Skeleton className="h-32" />;
  const h = analysis.health;
  if (!h) return <p className="text-sm text-ink-3">No device health for system events.</p>;
  const byHour = analysis.recurrence?.by_hour;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <HealthRing score={h.score} size={72} />
        <div>
          <h3>Health {h.grade}</h3>
          <p className="text-[13px] text-ink-3">
            Last {h.window_days} days: {sevs.slice(0, 3).map((s) => `${num(h.parts.events[s] || 0)} ${s}`).join(", ")}, {h.parts.flap_cycles} flap cycles, {h.parts.open_tickets} open tickets.
          </p>
        </div>
      </div>
      {byHour && (
        <div>
          <h4 className="mb-1.5 text-sm">When this device alerts (hour of day)</h4>
          <HourProfile values={byHour} highlight={event.ts ? Number(event.ts.slice(11, 13)) : -1} />
        </div>
      )}
    </div>
  );
}

export default function StageAnalysis({ detail, analysis }) {
  const { event: e, device: d, site } = detail;
  const extra = Object.entries(e.extra || {}).filter(([k]) => !HIDDEN_EXTRA.includes(k));
  const RoleIcon = d ? roleIcon(d.role) : null;
  return (
    <div>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="flex flex-col gap-3">
          {d ? (
            <Link to={`/devices/${d.id}`} className="flex items-center gap-3 rounded-xl border border-line p-3 text-ink hover:bg-hover hover:no-underline">
              <span className="grid size-10 place-items-center rounded-xl bg-brand-50 text-brand"><RoleIcon className="size-5" /></span>
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-mono text-[13.5px]">{d.name}</h3>
                <div className="flex gap-3 text-xs text-ink-2"><span className="font-mono">{d.ip || "no IP"}</span><span>{roleLabel(d.role)}</span></div>
              </div>
              <LuChevronRight className="size-4 text-ink-3" />
            </Link>
          ) : <Signal>This event is not tied to a device (monitoring-system or group notice).</Signal>}
          <KeyValue items={[
            d && ["Model", d.machine_type || "—"],
            d && ["Vendor", d.vendor || "—"],
            d && ["Node ID", d.node_id ?? "—"],
            d && ["Seen", `${stamp(d.first_seen)} to ${stamp(d.last_seen)}`],
            d && ["Events", num(d.event_count)],
            ["Site", site ? <><Link to={`/sites/${encodeURIComponent(site.code)}`}>{site.code} {site.label || ""}</Link><br /><span className="text-ink-3">{site.address || ""}</span></> : "Not identified"],
            ["Event type", `${e.type_id ?? "—"} ${e.name}`],
          ]} />
        </div>
        <Health analysis={analysis} event={e} />
      </div>
      {extra.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-[13px] text-ink-3">Other columns from the export ({extra.length})</summary>
          <KeyValue className="mt-2" items={extra.map(([k, v]) => [k, <span className="font-mono">{String(v)}</span>])} />
        </details>
      )}
    </div>
  );
}
