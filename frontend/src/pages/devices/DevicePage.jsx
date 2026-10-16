import { Link, useParams } from "react-router-dom";
import { LuWaves, LuTicket } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import AlertCard from "../../components/cards/AlertCard";
import TicketCard from "../../components/cards/TicketCard";
import ColumnsChart from "../../components/charts/ColumnsChart";
import HBars from "../../components/charts/HBars";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import HealthRing from "../../components/ui/HealthRing";
import LoadBoundary from "../../components/ui/LoadBoundary";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import { StatGrid, StatTile } from "../../components/ui/StatTile";
import { useLabels } from "../../context/AuthContext";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { roleLabel } from "../../lib/domain";
import { roleIcon } from "../../lib/icons";
import { address, dur, num, stamp } from "../../lib/format";

export default function DevicePage() {
  const { id } = useParams();
  const state = useAsync(() => inventoryApi.device(id), [id]);
  usePage(state.data?.device.name || "Device", [{ label: "Devices", to: "/devices" }]);
  return (
    <LoadBoundary state={state} notFound={{ title: "Device not found" }}>
      {(r) => <DeviceProfile r={r} id={id} />}
    </LoadBoundary>
  );
}

function DeviceProfile({ r, id }) {
  const labels = useLabels();
  const d = r.device, h = r.health, os = r.outage_summary;
  const RoleIcon = roleIcon(d.role);
  return (
    <div className="flex flex-col gap-4">
      <section className="overflow-hidden rounded-2xl border border-line bg-surface">
        <div className="h-1.5 bg-brand" />
        <div className="flex flex-wrap items-start gap-5 p-5 sm:p-6">
          <span className="grid size-14 flex-none place-items-center rounded-2xl bg-brand-50 text-brand"><RoleIcon className="size-7" /></span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-2">
              <Pill>{roleLabel(d.role)}</Pill>
              {d.status_label && <Pill tone={d.last_status === 2 ? "bad" : "neutral"}>Node {d.status_label}</Pill>}
              {r.flap_cycles >= 3 && <Pill tone="orange" icon={LuWaves}>Flapping</Pill>}
            </div>
            <h1 className="mt-2 break-all font-mono text-[clamp(20px,2.4vw,28px)]">{d.name}</h1>
            <div className="mt-1 text-sm text-ink-2">
              <span className="font-mono">{d.ip || "No IP"}</span>
              {d.site_code && <> in <Link to={`/sites/${encodeURIComponent(d.site_code)}`}>site {d.site_code} {d.site_label || ""}</Link></>}
            </div>
            <div className="mt-1 text-[13px] text-ink-3">{[d.machine_type, d.vendor, address(d.site_address)].filter(Boolean).join(", ") || "Model unknown"}</div>
          </div>
          <div className="flex items-center gap-3">
            <HealthRing score={h.score} size={76} />
            <div><b>{h.grade}</b><br /><span className="text-xs text-ink-3">Health over the {h.window_days} days<br />before its last event</span></div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-8" title="Activity by day" description="All events per day; red is critical.">
          <ColumnsChart rows={r.by_day} height={280} />
        </Panel>
        <Panel className="xl:col-span-4" title="Outages">
          <StatGrid cols="grid-cols-2">
            <StatTile value={num(os.closed)} label="Closed outages" />
            <StatTile value={dur(os.mttr_minutes)} label="Median recovery" />
            <StatTile value={num(os.open)} label="Still open" />
            <StatTile value={num(r.flap_cycles)} label="Short cycles (≤ 60 min)" />
          </StatGrid>
          <h4 className="mb-1 mt-4 text-sm">Latest outages</h4>
          <div className="max-h-56 overflow-y-auto">
            {r.outages.length ? r.outages.slice().reverse().map((o) => (
              <Link key={`${o.down_id}-${o.down_ts}`} to={`/alerts/${o.down_id}`} className="grid grid-cols-[1fr_auto_auto] gap-3 rounded-lg px-2 py-1.5 text-[13px] text-ink hover:bg-hover hover:no-underline">
                <span className="truncate">{o.name}</span><span className="text-ink-3">{stamp(o.down_ts)}</span><b>{dur(o.minutes)}</b>
              </Link>
            )) : <p className="text-sm text-ink-3">No paired outages.</p>}
          </div>
        </Panel>
        <Panel className="xl:col-span-6" title="Event types" actions={<Button size="sm" to={`/alerts?device_id=${id}&actionable=`}>All alerts</Button>}>
          <HBars items={r.by_type} getKey={(x) => x.name} label={(x) => x.name}
            sub={(x) => `${x.severity} ${labels.severity(x.severity)}, last ${stamp(x.last)}`} />
        </Panel>
        <Panel className="xl:col-span-6" title="Linked tickets" description="Tickets that name this device, its IP or configuration item.">
          {r.tickets.length ? <div className="flex flex-col gap-2.5">{r.tickets.map((t) => <TicketCard key={t.number} ticket={{ ...t, links: 1 }} />)}</div>
            : <EmptyState icon={LuTicket} title="No linked tickets" text="No ticket mentions this device yet." />}
        </Panel>
        <Panel className="xl:col-span-8" title="Latest events">
          {r.recent.length ? (
            <div className="flex flex-col gap-1.5">
              {r.recent.map((e) => <AlertCard key={e.id} compact alert={{ ...e, device_name: d.name, ip: d.ip, site_code: d.site_code, site_label: d.site_label }} />)}
            </div>
          ) : <p className="text-sm text-ink-3">No events recorded.</p>}
        </Panel>
        <Panel className="xl:col-span-4" title="Same site">
          {r.peers.length ? r.peers.map((p) => {
            const Icon = roleIcon(p.role);
            return (
              <Link key={p.id} to={`/devices/${p.id}`} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-ink hover:bg-hover hover:no-underline">
                <Icon className="size-4 text-brand" /><span className="flex-1 truncate font-mono text-[12.5px]">{p.name}</span>
                <span className="font-mono text-[11.5px] text-ink-3">{p.ip || ""}</span>
              </Link>
            );
          }) : <p className="text-sm text-ink-3">No other devices at this site.</p>}
        </Panel>
      </div>
    </div>
  );
}
