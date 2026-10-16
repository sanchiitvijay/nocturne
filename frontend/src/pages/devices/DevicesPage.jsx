import { LuCpu, LuMapPin, LuNetwork, LuServer } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import DeviceCard from "../../components/cards/DeviceCard";
import { Select } from "../../components/ui/Field";
import ListView from "../../components/ui/ListView";
import ResultLine from "../../components/ui/ResultLine";
import SearchFilters from "../../components/ui/SearchFilters";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { useUrlState } from "../../hooks/useUrlState";
import { roleLabel } from "../../lib/domain";
import { num } from "../../lib/format";

const SORTS = [["events", "Most events"], ["recent", "Recently active"], ["name", "Name A–Z"]];

const SEARCH_FIELDS = [
  { id: "name", label: "Device name", placeholder: "Search device name…", icon: LuServer },
  { id: "ip", label: "IP address", placeholder: "IP, e.g. 10.14", icon: LuNetwork },
  { id: "model", label: "Model", placeholder: "Model or type", icon: LuCpu },
  { id: "site", label: "Site code", placeholder: "Site, e.g. 0412", icon: LuMapPin },
];

export default function DevicesPage() {
  usePage("Devices");
  const [f, setF] = useUrlState({ name: "", ip: "", model: "", site: "", q: "", role: "", sort: "events", page: 1 });
  const state = useAsync(() => inventoryApi.devices(f), [JSON.stringify(f)]);
  const d = state.data;

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-line bg-surface p-3 sm:p-4">
        <SearchFilters fields={SEARCH_FIELDS} values={Object.fromEntries(SEARCH_FIELDS.map((x) => [x.id, f[x.id]]))}
          onChange={(v) => setF({ ...v, q: "", page: 1 })}>
          <div className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <Select className="h-9 w-auto flex-1 text-[13px] sm:flex-none" aria-label="Role" value={f.role} onChange={(e) => setF({ role: e.target.value, page: 1 })}>
              <option value="">All roles</option>
              {(d?.roles || []).map((r) => <option key={r.role} value={r.role}>{roleLabel(r.role)} ({num(r.n)})</option>)}
            </Select>
            <Select className="h-9 w-auto flex-1 text-[13px] sm:flex-none" aria-label="Sort" value={f.sort} onChange={(e) => setF({ sort: e.target.value, page: 1 })}>
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </div>
        </SearchFilters>
      </section>
      <ResultLine>
        {d && <span><b className="text-ink">{num(d.total)}</b> devices</span>}
        <span className="text-ink-3">The dot shows the last node state: red down, green up.</span>
      </ResultLine>
      <ListView state={state} onPage={(page) => setF({ page })} renderItem={(x) => <DeviceCard key={x.id} device={x} />}
        empty={{ icon: LuCpu, title: "No devices match", text: "Clear the search fields or pick another role." }} />
    </div>
  );
}
