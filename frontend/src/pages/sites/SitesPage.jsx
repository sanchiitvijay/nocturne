import { LuMapPin, LuX } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import SiteCard from "../../components/cards/SiteCard";
import Tilegram from "../../components/charts/Tilegram";
import { Chip, ChipRow } from "../../components/ui/Chip";
import ListView from "../../components/ui/ListView";
import Panel from "../../components/ui/Panel";
import ResultLine from "../../components/ui/ResultLine";
import SearchInput from "../../components/ui/SearchInput";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatGrid, StatTile } from "../../components/ui/StatTile";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { useUrlState } from "../../hooks/useUrlState";
import { compact, num } from "../../lib/format";

export default function SitesPage() {
  usePage("Sites");
  const [f, setF] = useUrlState({ q: "", state: "", page: 1 });
  const state = useAsync(() => inventoryApi.sites(f), [JSON.stringify(f)]);
  const d = state.data;
  const states = d?.states || [];
  const top = [...states].sort((a, b) => b.alerts - a.alerts).slice(0, 10);
  const tot = states.reduce((a, s) => ({ sites: a.sites + s.sites, alerts: a.alerts + s.alerts, p1: a.p1 + (s.p1 || 0) }), { sites: 0, alerts: 0, p1: 0 });
  const pick = (st) => setF({ state: st, page: 1 });

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-12">
        <Panel className="lg:col-span-5" title="Sites by state" description="Select a state to list its sites. Darker tiles carry more actionable alerts.">
          {d ? <Tilegram states={states.map((s) => ({ ...s, n: s.alerts }))} onPick={pick} selected={f.state} /> : <Skeleton className="h-52" />}
        </Panel>
        <Panel className="lg:col-span-7" bodyClassName="flex flex-col gap-4">
          <SearchInput value={f.q} onSearch={(q) => setF({ q, page: 1 })} placeholder="Site code, city or address…" />
          <ChipRow label="Busiest">
            {top.map((s) => <Chip key={s.state} on={f.state === s.state} count={s.alerts} onClick={() => pick(f.state === s.state ? "" : s.state)}>{s.state}</Chip>)}
            {f.state && <Chip trailing={LuX} onClick={() => pick("")}>Clear</Chip>}
          </ChipRow>
          {d ? (
            <StatGrid>
              <StatTile value={num(tot.sites)} label="Sites with a state" />
              <StatTile value={num(states.length)} label="States covered" />
              <StatTile value={compact(tot.alerts)} label="Actionable alerts" />
              <StatTile value={compact(tot.p1)} label="Critical" />
            </StatGrid>
          ) : <Skeleton className="h-20" />}
        </Panel>
      </div>
      <ResultLine>
        {d && <span><b className="text-ink">{num(d.total)}</b> sites{f.state ? ` in ${f.state}` : ""}</span>}
        <span className="text-ink-3">Sorted by actionable alerts.</span>
      </ResultLine>
      <ListView state={state} onPage={(page) => setF({ page })} renderItem={(s) => <SiteCard key={s.code} site={s} />}
        empty={{ icon: LuMapPin, title: "No sites match", text: "Site codes come from device names during import." }} />
    </div>
  );
}
