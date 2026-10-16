import { LuTicket, LuHash, LuMessageSquare, LuFileText } from "react-icons/lu";
import { inventoryApi } from "../../api/endpoints";
import TicketCard from "../../components/cards/TicketCard";
import { Select } from "../../components/ui/Field";
import ListView from "../../components/ui/ListView";
import ResultLine from "../../components/ui/ResultLine";
import SearchFilters from "../../components/ui/SearchFilters";
import Segmented from "../../components/ui/Segmented";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import { useUrlState } from "../../hooks/useUrlState";
import { num } from "../../lib/format";

const STATUS = [["", "All"], ["open", "Open"], ["closed", "Closed"]];
const LINKED = [["", "All"], ["yes", "Linked to inventory"], ["no", "Not linked"]];

const SEARCH_FIELDS = [
  { id: "number", label: "Ticket number", placeholder: "Ticket, e.g. INC0123", icon: LuHash },
  { id: "description", label: "Description", placeholder: "Search description…", icon: LuMessageSquare },
  { id: "work_notes", label: "Work notes", placeholder: "Search work notes…", icon: LuFileText },
];

export default function TicketsPage() {
  usePage("Tickets");
  const [f, setF] = useUrlState({ number: "", description: "", work_notes: "", q: "", kind: "", status: "", linked: "", page: 1 });
  const state = useAsync(() => inventoryApi.tickets(f), [JSON.stringify(f)]);
  const d = state.data;

  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-3 sm:p-4">
        <SearchFilters fields={SEARCH_FIELDS} values={Object.fromEntries(SEARCH_FIELDS.map((x) => [x.id, f[x.id]]))}
          onChange={(v) => setF({ ...v, q: "", page: 1 })} />
        <div className="flex flex-wrap items-center gap-2">
          <Segmented size="sm" label="Status" value={f.status} onChange={(v) => setF({ status: v, page: 1 })}
            options={STATUS.map(([v, l]) => ({ value: v, label: l }))} />
          <Select className="h-8 w-auto text-[13px]" aria-label="Type" value={f.kind} onChange={(e) => setF({ kind: e.target.value, page: 1 })}>
            <option value="">All types</option>
            {(d?.kinds || []).map((k) => <option key={k.kind} value={k.kind}>{k.kind} ({num(k.n)})</option>)}
          </Select>
          <Select className="h-8 w-auto text-[13px]" aria-label="Linked" value={f.linked} onChange={(e) => setF({ linked: e.target.value, page: 1 })}>
            {LINKED.map(([v, l]) => <option key={v} value={v}>{v ? l : "Linked or not"}</option>)}
          </Select>
        </div>
      </section>
      <ResultLine>
        {d && <span><b className="text-ink">{num(d.total)}</b> tickets</span>}
        <span className="text-ink-3">Green boxes show what fixed it, pulled from close and work notes.</span>
      </ResultLine>
      <ListView state={state} onPage={(page) => setF({ page })} renderItem={(t) => <TicketCard key={t.id} ticket={t} />}
        empty={{ icon: LuTicket, title: "No tickets match", text: "Clear the search fields or change the filters." }} />
    </div>
  );
}
