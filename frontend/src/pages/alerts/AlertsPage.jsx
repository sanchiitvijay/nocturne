import { useCallback, useMemo, useState } from "react";
import { LuBell, LuRefreshCw } from "react-icons/lu";
import { alertsApi } from "../../api/endpoints";
import AlertCard from "../../components/cards/AlertCard";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import Pager from "../../components/ui/Pager";
import { SkeletonList } from "../../components/ui/Skeleton";
import { useAuth } from "../../context/AuthContext";
import { useLive, useLiveEvent } from "../../context/LiveContext";
import { usePage } from "../../context/PageContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";
import { useAsync } from "../../hooks/useAsync";
import { useStoredState } from "../../hooks/useStoredState";
import { useUrlState } from "../../hooks/useUrlState";
import { num, stamp } from "../../lib/format";
import AlertFilters from "./AlertFilters";
import BulkBar from "./BulkBar";

const SCHEMA = {
  event_id: "", text: "", device: "", ip: "", site: "",
  q: "", window: "all", sort: "newest", page: 1, severity: [], category: [], state: [], source: [],
  actionable: "1", device_id: "", type_id: "", hour: "",
};
const MAX_LIVE_ITEMS = 60;

/** Does a live alert belong in the current view? Text, site, type and hour filters need the server, so they say no. */
function matches(f, e) {
  if (f.severity.length && !f.severity.includes(e.severity)) return false;
  if (f.category.length && !f.category.includes(e.category)) return false;
  if (f.state.length && !f.state.includes(e.state)) return false;
  if (f.source.length && !f.source.includes(e.source)) return false;
  if (f.actionable !== "" && String(e.actionable) !== f.actionable) return false;
  if (f.device_id && String(e.device_id) !== f.device_id) return false;
  // Text search and site/device filters need the server
  return !(f.q || f.text || f.device || f.ip || f.site || f.type_id || f.hour !== "");
}

export default function AlertsPage() {
  usePage("Alerts");
  const { can } = useAuth();
  const toast = useToast();
  const { resetNew } = useLive();
  const [filters, setFilters] = useUrlState(SCHEMA);
  const [view, setView] = useStoredState("nocturne-view", "cards");
  const [selected, setSelected] = useState(() => new Set());
  const [fresh, setFresh] = useState(() => new Set());
  const [pending, setPending] = useState(0);
  const params = useMemo(() => { const { page, ...rest } = filters; return { ...rest, page }; }, [filters]);
  const key = JSON.stringify(params);

  const state = useAsync(async ({ background }) => {
    const r = await alertsApi.list(params, { background });
    setPending(0);
    resetNew();
    return r;
     
  }, [key]);
  const { data, error, loading, setData } = state;
  const selectable = can("update_alert_state");

  useLiveEvent("alert", (e) => {
    if (!matches(filters, e)) return;
    if (filters.page === 1 && filters.sort === "newest" && data) {
      setData((d) => ({ ...d, total: d.total + 1, items: [{ ...e, tickets: 0, repeats: 1 }, ...d.items.filter((x) => x.id !== e.id)].slice(0, MAX_LIVE_ITEMS) }));
      setFresh((s) => new Set(s).add(e.id));
      resetNew();
    } else {
      setPending((n) => n + 1);
    }
  });
  useLiveEvent("alert_state", (s) => {
    setData((d) => (d ? { ...d, items: d.items.map((x) => (x.id === s.id ? { ...x, state: s.state, owner: s.owner } : x)) } : d));
  });

  const onSelect = useCallback((id, on) => setSelected((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; }), []);
  const [applyBulk, bulkBusy] = useAction(async (target) => {
    const r = await alertsApi.bulkState([...selected], target);
    toast(`${num(r.updated)} alert${r.updated === 1 ? "" : "s"} marked ${target}.`, "ok");
    setSelected(new Set());
    await state.reload({ background: true });
  });
  const showNewest = () => setFilters({ page: 1, sort: "newest" });

  return (
    <div className="flex flex-col gap-4 pb-20">
      <AlertFilters filters={filters} setFilters={setFilters} facets={data?.facets} view={view} setView={setView}
        exportHref={alertsApi.exportUrl({ ...params, page: undefined })} />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-ink-2">
        {data && <span><b className="text-ink">{num(data.total)}</b> alert{data.total === 1 ? "" : "s"} match</span>}
        {data?.as_of && <span>Data as of {stamp(data.as_of)}</span>}
        <span className="text-ink-3">Time windows count back from the newest event.</span>
        {pending > 0 && (
          <Button size="sm" variant="primary" icon={LuRefreshCw} onClick={showNewest} className="ml-auto">
            {pending} new alert{pending > 1 ? "s" : ""}, show newest
          </Button>
        )}
      </div>

      {error && !data ? <ErrorState error={error} onRetry={() => state.reload()} />
        : !data ? <SkeletonList count={9} className={view === "compact" ? "h-12" : "h-48"} grid={view !== "compact"} />
          : data.items.length === 0
            ? <EmptyState icon={LuBell} title="No alerts match these filters" text="Widen the time window, clear a filter, or switch “Show” to Everything." />
            : (
              <div className={`transition-opacity ${loading ? "opacity-60" : ""} ${view === "compact" ? "flex flex-col gap-1.5" : "grid gap-3 sm:grid-cols-2 2xl:grid-cols-3"}`}>
                {data.items.map((e) => (
                  <AlertCard key={e.id} alert={e} compact={view === "compact"} selectable={selectable}
                    selected={selected.has(e.id)} onSelect={onSelect} fresh={fresh.has(e.id)} />
                ))}
              </div>
            )}
      {data && <Pager total={data.total} page={data.page} size={data.size} onPage={(p) => setFilters({ page: p })} />}
      {selectable && <BulkBar count={selected.size} busy={bulkBusy} onApply={applyBulk} onClear={() => setSelected(new Set())} />}
    </div>
  );
}
