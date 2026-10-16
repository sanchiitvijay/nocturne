import { useParams } from "react-router-dom";
import { LuArrowDown, LuBell, LuCpu, LuTicket } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import AlertCard from "../../components/cards/AlertCard";
import DeviceCard from "../../components/cards/DeviceCard";
import TicketCard from "../../components/cards/TicketCard";
import ColumnsChart from "../../components/charts/ColumnsChart";
import HBars from "../../components/charts/HBars";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import LoadBoundary from "../../components/ui/LoadBoundary";
import Panel from "../../components/ui/Panel";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { address, cap, compact } from "../../lib/format";

export default function SitePage() {
  const { code } = useParams();
  const state = useAsync(() => inventoryApi.site(code), [code]);
  const s = state.data?.site;
  usePage(s ? `Site ${s.code}${s.label ? `, ${s.label}` : ""}` : `Site ${code}`, [{ label: "Sites", to: "/sites" }]);
  return (
    <LoadBoundary state={state} notFound={{ title: "Site not found" }}>
      {(r) => <SiteProfile r={r} />}
    </LoadBoundary>
  );
}

function SiteProfile({ r }) {
  const s = r.site;
  const down = r.devices.filter((d) => d.node_state === "down").length;
  const alerts = r.by_category.reduce((a, c) => a + c.n, 0);
  const enc = encodeURIComponent(s.code);
  const kpis = [
    { icon: LuCpu, label: "Devices", value: r.devices.length },
    { icon: LuArrowDown, label: "Last seen down", value: down, alarm: down > 0 },
    { icon: LuBell, label: "Actionable alerts", value: compact(alerts) },
    { icon: LuTicket, label: "Linked tickets", value: r.tickets.length },
  ];
  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl bg-[#00446a] p-5 text-white sm:p-7 dark:bg-[#0f2a3e]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-mono text-3xl text-white">{s.code}</h1>
            <div className="mt-1 text-sm text-white/80"><b>{s.label || "Unlabelled site"}</b>{address(s.address) ? `, ${address(s.address)}` : ""}</div>
          </div>
          <Button variant="onBrand" icon={LuBell} to={`/alerts?site=${enc}&actionable=1`}>Site alerts</Button>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-2.5 md:grid-cols-4">
          {kpis.map((k) => (
            <div key={k.label} className={`rounded-xl border p-3.5 ${k.alarm ? "border-[#ff9aa6]/50 bg-[#c8102e]/20" : "border-white/15 bg-white/[0.07]"}`}>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-white/75"><k.icon className="size-4" />{k.label}</div>
              <div className={`mt-1.5 text-[28px] font-bold leading-none ${k.alarm ? "text-[#ff9aa6]" : ""}`}>{k.value}</div>
            </div>
          ))}
        </div>
      </section>
      <div className="grid gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-8" title="Alerts per day"><ColumnsChart rows={r.by_day} /></Panel>
        <Panel className="xl:col-span-4" title="By category">
          <HBars items={r.by_category} getKey={(x) => x.category} label={(x) => cap(x.category)} href={(x) => `/alerts?site=${enc}&category=${x.category}&actionable=1`} />
        </Panel>
        <Panel className="xl:col-span-12" title="Devices" description="Red dots were last seen down.">
          {r.devices.length ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{r.devices.map((d) => <DeviceCard key={d.id} device={d} showSite={false} />)}</div>
            : <EmptyState icon={LuCpu} title="No devices" />}
        </Panel>
        <Panel className="xl:col-span-7" title="Latest alerts">
          {r.recent.length ? <div className="flex flex-col gap-1.5">{r.recent.map((e) => <AlertCard key={e.id} compact alert={{ ...e, site_code: s.code, site_label: s.label }} />)}</div>
            : <EmptyState icon={LuBell} title="No alerts" />}
        </Panel>
        <Panel className="xl:col-span-5" title="Tickets mentioning this site">
          {r.tickets.length ? <div className="flex flex-col gap-2.5">{r.tickets.map((t) => <TicketCard key={t.number} ticket={{ ...t, links: 1 }} />)}</div>
            : <EmptyState icon={LuTicket} title="No tickets mention this site" />}
        </Panel>
      </div>
    </div>
  );
}
