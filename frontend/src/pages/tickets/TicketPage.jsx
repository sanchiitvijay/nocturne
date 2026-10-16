import { Link, useParams } from "react-router-dom";
import { LuActivity, LuCheck, LuClock, LuUser } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import KeyValue from "../../components/ui/KeyValue";
import Kind from "../../components/ui/Kind";
import LoadBoundary from "../../components/ui/LoadBoundary";
import Meter from "../../components/ui/Meter";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import Signal from "../../components/ui/Signal";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { kindColor } from "../../lib/domain";
import { date, dur, stamp } from "../../lib/format";

const LINK_KIND = { ci: "Configuration item", device: "Name in text", ip: "IP in text", site: "Site / FEI code in text" };

/** One row per device or site, with every way it was matched and the best time evidence. */
function groupLinks(links) {
  const by = new Map();
  links.forEach((l) => {
    const key = l.device_id ? `d${l.device_id}` : `s${l.site_code}`;
    const g = by.get(key) || { ...l, kinds: [], confidence: 0, evidence: null };
    g.kinds.push({ kind: l.kind, value: l.value });
    g.confidence = Math.max(g.confidence, l.confidence);
    if (l.evidence === "confirmed" || (!g.evidence && l.evidence)) {
      Object.assign(g, { evidence: l.evidence, gap_minutes: l.gap_minutes, event_id: l.event_id, event_name: l.event_name, event_severity: l.event_severity, event_ts: l.event_ts });
    }
    by.set(key, g);
  });
  return [...by.values()].sort((a, b) => b.confidence - a.confidence);
}

export default function TicketPage() {
  const { number } = useParams();
  const state = useAsync(() => inventoryApi.ticket(number), [number]);
  const t = state.data?.ticket;
  usePage(t ? `${t.number} ${t.short_description || ""}` : number, [{ label: "Tickets", to: "/tickets" }]);
  return (
    <LoadBoundary state={state} notFound={{ title: "Ticket not found" }}>
      {(r) => <TicketDetail r={r} />}
    </LoadBoundary>
  );
}

function TicketDetail({ r }) {
  const t = r.ticket;
  const anchor = t.incident_start ? "the stated start" : "opening";
  const gap = (m) => `${Math.abs(m) < 120 ? `${Math.abs(m)} min` : `${(Math.abs(m) / 60).toFixed(1)} h`} ${m >= 0 ? "before" : "after"} ${anchor}`;
  const groups = groupLinks(r.links);
  const c = r.event_coverage || {};
  const showCoverage = r.links.length && c.first && t.created_at && !r.links.some((l) => l.evidence);

  return (
    <div className="flex flex-col gap-4">
      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="h-1.5" style={{ background: kindColor(t.kind) }} />
        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Kind kind={t.kind} /><b className="font-mono">{t.number}</b>
            <Pill tone={t.is_open ? "bad" : "good"}>{t.state || ""}</Pill>
            {t.priority && <Pill>Priority {t.priority}</Pill>}
          </div>
          <h1 className="mt-2.5 text-[clamp(20px,2.4vw,28px)]">{t.short_description || "No description"}</h1>
          <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[13.5px] text-ink-3">
            {t.incident_start && <span className="flex items-center gap-1" title="Start time written in the ticket, checked against when it was opened"><LuActivity className="size-4" />Incident started {stamp(t.incident_start)}</span>}
            <span className="flex items-center gap-1"><LuClock className="size-4" />Opened {t.created_at ? stamp(t.created_at) : "date unknown"}</span>
            {t.closed_at && <span>Closed {stamp(t.closed_at)} ({dur(t.resolve_minutes)})</span>}
            {t.assignment_group && <span>{t.assignment_group}</span>}
            {t.assigned_to && <span className="flex items-center gap-1"><LuUser className="size-4" />{t.assigned_to}</span>}
            {t.opened_by && <span>Opened by {t.opened_by}</span>}
          </div>
        </div>
      </section>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          {t.fixes.length > 0 && (
            <Panel title="What fixed it" description="Sentences from the notes that describe actions taken.">
              <div className="flex flex-col gap-2">{t.fixes.map((f, i) => <div key={i} className="rounded-lg bg-good-bg px-3 py-2 text-[13.5px] text-good-ink">{f}</div>)}</div>
            </Panel>
          )}
          <Panel title="Description"><div className="whitespace-pre-wrap text-sm">{t.description || "—"}</div></Panel>
          <Panel title="Work notes" description={`${t.entries.length} entries, newest first.`}>
            {t.entries.length ? (
              <div className="flex flex-col">
                {t.entries.map((e, i) => (
                  <div key={i} className="grid grid-cols-[110px_1fr] gap-3 border-b border-line py-2.5 last:border-0">
                    <span className="text-xs tabular-nums text-ink-3">{e.at ? stamp(e.at) : ""}</span>
                    <span className="whitespace-pre-wrap border-l-2 border-brand pl-3 text-[13.5px]">{e.text}</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-ink-3">No work notes.</p>}
          </Panel>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <Panel title="Linked inventory" description="How this ticket was tied to devices and sites, and whether alert timing backs it up.">
            {showCoverage && (
              <Signal className="mb-3">Alert timing cannot confirm these links: event data covers {date(c.first)} – {date(c.last)}, and this ticket was opened {date(t.created_at)}.</Signal>
            )}
            {groups.length ? groups.map((g) => (
              <div key={g.device_id ? `d${g.device_id}` : `s${g.site_code}`} className="flex items-center gap-3 border-b border-line py-2.5 last:border-0">
                <div className="min-w-0 flex-1">
                  {g.device_id
                    ? <Link className="block truncate font-mono text-[13px]" to={`/devices/${g.device_id}`}>{g.device_name}</Link>
                    : <Link to={`/sites/${encodeURIComponent(g.site_code)}`}>Site {g.site_code} {g.site_label || ""}</Link>}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {g.kinds.map((k, i) => <Pill key={i} title={k.value}>{LINK_KIND[k.kind] || k.kind}</Pill>)}
                    {g.evidence === "confirmed" && (
                      <Link to={`/alerts/${g.event_id}`} title={`${g.event_name || ""} ${stamp(g.event_ts)}`}>
                        <Pill tone="good" icon={LuCheck}>{g.event_severity || ""} alert {gap(g.gap_minutes)}</Pill>
                      </Link>
                    )}
                    {g.evidence === "no_alerts" && <Pill tone="bad" title="Event data covers this window">No alerts around opening</Pill>}
                  </div>
                </div>
                <div className="flex w-28 items-center gap-2 text-xs font-semibold tabular-nums">
                  <Meter value={g.confidence * 100} />{Math.round(g.confidence * 100)}%
                </div>
              </div>
            )) : <p className="text-sm text-ink-3">Not linked: no device name, IP or site code found in the text.</p>}
          </Panel>
          <Panel title="Extracted facts">
            <KeyValue items={[
              ["Sites", t.sites.length ? <span className="flex flex-wrap gap-x-2">{t.sites.map((s) => <Link key={s} to={`/sites/${encodeURIComponent(s)}`}>{s}</Link>)}</span> : "—"],
              ["IP addresses", <span className="font-mono">{t.ips.join(", ") || "—"}</span>],
              ["Devices", <span className="font-mono">{t.devices.join(", ") || "—"}</span>],
              ...Object.entries(t.extra || {}).map(([k, v]) => [k, String(v)]),
            ]} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
