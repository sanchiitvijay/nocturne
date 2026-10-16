import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LuCircleCheck } from "react-icons/lu";
import { qs } from "../../api/client";
import { inventoryApi } from "../../api/endpoints";
import AlertCard from "../../components/cards/AlertCard";
import HBars from "../../components/charts/HBars";
import ScoreChart from "../../components/charts/ScoreChart";
import SegBar, { Legend } from "../../components/charts/SegBar";
import Tilegram from "../../components/charts/Tilegram";
import VolumeChart from "../../components/charts/VolumeChart";
import { useSeverityKeys } from "../../components/charts/useSeverityKeys";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import Panel from "../../components/ui/Panel";
import Segmented from "../../components/ui/Segmented";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth, useLabels } from "../../context/AuthContext";
import { useLiveEvent } from "../../context/LiveContext";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { useDebouncedCallback } from "../../hooks/useDebounce";
import { useStoredState } from "../../hooks/useStoredState";
import { useUrlState } from "../../hooks/useUrlState";
import { sevColor, roleLabel } from "../../lib/domain";
import { cap, compact, num, parseTs, stamp } from "../../lib/format";
import KpiStrip from "./KpiStrip";
import TicketKnowledge from "./TicketKnowledge";

function AsOf({ w }) {
  if (!w?.as_of) return <>No events yet. Import data in Data Studio or run the simulator.</>;
  const days = w.start && w.end ? Math.round((parseTs(w.end) - parseTs(w.start)) / 864e5) : null;
  return (
    <>Data as of <b>{stamp(w.as_of)}</b>
      {w.start ? `, showing ${days >= 1 ? `${days} day${days > 1 ? "s" : ""}` : "the last 24 hours"} up to then.` : ", showing everything imported."}</>
  );
}

export default function DashboardPage() {
  usePage("Overview");
  const { lookups, can } = useAuth();
  const labels = useLabels();
  const sevs = useSeverityKeys();
  const navigate = useNavigate();
  const [storedWindow, setStoredWindow] = useStoredState("nocturne-window", "7d");
  const [url, setUrl] = useUrlState({ window: "" });
  const windowSel = url.window || storedWindow;
  const windows = (lookups.windows || []).map((w) => ({ value: w.id, label: w.label }));

  const state = useAsync(({ background }) => inventoryApi.overview({ window: windowSel }, { background }), [windowSel]);
  const { data: d, error } = state;
  const refresh = useDebouncedCallback(() => state.reload({ background: true }), 2500);
  useLiveEvent("alert", refresh);
  useLiveEvent("data", refresh);
  useLiveEvent("alert_state", refresh);

  const pickWindow = (w) => { setStoredWindow(w); setUrl({ window: w }); };
  const alertsHref = useCallback((extra) => `/alerts${qs({ window: windowSel, actionable: 1, ...extra })}`, [windowSel]);
  useEffect(() => { if (url.window && url.window !== storedWindow) setStoredWindow(url.window); }, [url.window, storedWindow, setStoredWindow]);

  if (error && !d) return <ErrorState error={error} onRetry={() => state.reload()} />;

  return (
    <div className={`flex flex-col gap-4 transition-opacity ${state.loading && d ? "opacity-60" : ""}`}>
      <section className="rounded-2xl bg-[#00446a] p-5 text-white sm:p-7 dark:bg-[#0f2a3e]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="animate-rise text-3xl text-white">Network pulse</h1>
            <div className="mt-1 animate-rise text-sm text-white/75">{d ? <AsOf w={d.window} /> : "Loading the latest data…"}</div>
          </div>
          <Segmented tone="onBrand" label="Time window" options={windows} value={windowSel} onChange={pickWindow} />
        </div>
        {d ? <KpiStrip kpis={d.kpis} previous={d.previous || {}} alertsHref={alertsHref} />
          : <div className="mt-6 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }, (_, i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white/10" />)}</div>}
      </section>

      <div className="grid gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-8" title="Alerts by hour of day"
          description="Actionable alerts by hour of day and category. Bigger dots mean more alerts; colour is the worst severity in that hour. Select a dot to open those alerts.">
          {d ? <>
            <ScoreChart rows={d.score} onPick={(category, hour) => navigate(alertsHref({ category, hour }))} />
            <Legend items={sevs.slice(0, 3).map((s) => ({ label: `${s} ${labels.severity(s)}`, color: sevColor(s), round: true }))} note="Dot size grows with alert count" />
          </> : <Skeleton className="h-64" />}
        </Panel>
        <Panel className="xl:col-span-4" title="Needs attention" description="Latest unresolved critical and major alerts."
          actions={can("view_alerts") && <Button size="sm" to={`/alerts${qs({ severity: "P1,P2", state: "new,acknowledged", actionable: 1 })}`}>All open</Button>}>
          {d ? (d.hot.length
            ? <div className="flex max-h-[520px] flex-col gap-2 overflow-y-auto pr-1">{d.hot.map((e) => <AlertCard key={e.id} alert={e} compact />)}</div>
            : <EmptyState icon={LuCircleCheck} title="Nothing critical is open" text="Critical and major alerts that are not resolved show up here." />)
            : <Skeleton className="h-64" />}
        </Panel>

        <Panel className="xl:col-span-8" title="Alert volume" description={d ? `Events per ${d.bucket}, stacked by severity.` : "Events over time, stacked by severity."}>
          {d ? <>
            <VolumeChart rows={d.volume} bucket={d.bucket} />
            <Legend items={sevs.map((s) => ({ label: `${s} ${labels.severity(s)}`, color: sevColor(s), value: compact(d.severity[s] || 0) }))} />
          </> : <Skeleton className="h-56" />}
        </Panel>
        <Panel className="xl:col-span-4" title="Alerts by state" description="Actionable alerts by US state. Darker tiles carry more alerts; select one to list its sites.">
          {d ? <>
            <Tilegram states={d.by_state} onPick={(st) => navigate(`/sites?state=${st}`)} />
            <div className="mt-5"><SegBar parts={sevs.map((s) => ({ label: `${s} ${labels.severity(s)}`, value: d.severity[s] || 0, color: sevColor(s) }))} /></div>
          </> : <Skeleton className="h-56" />}
        </Panel>

        <Panel className="xl:col-span-4" title="Noisiest devices" actions={<Button size="sm" to="/devices">Devices</Button>}>
          {d ? <HBars items={d.top_devices} getKey={(x) => x.id} label={(x) => x.name} href={(x) => `/devices/${x.id}`}
            sub={(x) => `${roleLabel(x.role)}${x.site_code ? `, site ${x.site_code}` : ""}${x.flapping ? `, flapping ×${x.flapping}` : ""}`} /> : <Skeleton className="h-48" />}
        </Panel>
        <Panel className="xl:col-span-4" title="Busiest sites" actions={<Button size="sm" to="/sites">Sites</Button>}>
          {d ? <HBars items={d.top_sites} getKey={(x) => x.code} label={(x) => `${x.code} ${x.label || ""}`} href={(x) => `/sites/${encodeURIComponent(x.code)}`}
            sub={(x) => `${x.devices} devices alerting, ${num(x.p1)} critical`} /> : <Skeleton className="h-48" />}
        </Panel>
        <Panel className="xl:col-span-4" title="Top event types">
          {d ? <HBars items={d.top_types} getKey={(x) => `${x.type_id}-${x.name}`} label={(x) => x.name} href={(x) => alertsHref({ type_id: x.type_id, actionable: "" })}
            sub={(x) => `${x.severity} ${labels.severity(x.severity)}, ${x.category}`} /> : <Skeleton className="h-48" />}
        </Panel>

        <Panel className="xl:col-span-6" title="Categories" description="All events per category; the darker part is actionable.">
          {d ? <HBars items={d.categories} getKey={(x) => x.category} label={(x) => cap(x.category)} alt={(x) => x.actionable || 0}
            href={(x) => alertsHref({ category: x.category, actionable: "" })} sub={(x) => `${compact(x.actionable || 0)} actionable`} /> : <Skeleton className="h-48" />}
        </Panel>
        <Panel className="xl:col-span-6" title="Ticket knowledge" description="Service-desk history the recommendations learn from."
          actions={can("view_tickets") && <Button size="sm" to="/tickets">Tickets</Button>}>
          {d ? <TicketKnowledge tickets={d.tickets} /> : <Skeleton className="h-48" />}
        </Panel>
      </div>
    </div>
  );
}
