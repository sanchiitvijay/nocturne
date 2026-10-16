import { useState } from "react";
import { adminApi } from "../../api/endpoints";
import { Chip } from "../../components/ui/Chip";
import ErrorState from "../../components/ui/ErrorState";
import Pager from "../../components/ui/Pager";
import Panel from "../../components/ui/Panel";
import Pill from "../../components/ui/Pill";
import SearchInput from "../../components/ui/SearchInput";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAsync } from "../../hooks/useAsync";
import { stamp } from "../../lib/format";

const PAGE_SIZE = 40;

export default function AuditTab() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => adminApi.audit({ q, page, size: PAGE_SIZE }), [q, page]);
  const search = (value) => { setQ(value); setPage(1); };

  return (
    <Panel title="Audit trail" actions={<SearchInput className="w-72 flex-none" value={q} onSearch={search} placeholder="Filter by person, action or target…" />}>
      {data && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {data.actions.map((a) => <Chip key={a.action} on={q === a.action} count={a.n} onClick={() => search(q === a.action ? "" : a.action)}>{a.action}</Chip>)}
        </div>
      )}
      {error && !data ? <ErrorState error={error} onRetry={() => reload()} /> : !data ? <Skeleton className="h-80" /> : (
        <>
          <div className={`overflow-x-auto rounded-xl border border-line transition-opacity ${loading ? "opacity-60" : ""}`}>
            <table className="w-full min-w-[820px] text-left text-[13px]">
              <thead className="bg-surface-2 text-xs uppercase tracking-wide text-ink-3">
                <tr>{["When", "Who", "Action", "Target", "Detail", "IP"].map((h) => <th key={h} className="px-3 py-2.5">{h}</th>)}</tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id} className="border-t border-line align-top">
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">{stamp(i.at)}</td>
                    <td className="px-3 py-2">{i.username || ""}</td>
                    <td className="px-3 py-2"><Pill>{i.action}</Pill></td>
                    <td className="px-3 py-2 break-all">{i.target || ""}</td>
                    <td className="max-w-[420px] px-3 py-2 text-ink-3">{(i.detail || "").slice(0, 200)}</td>
                    <td className="px-3 py-2 font-mono">{i.ip || ""}</td>
                  </tr>
                ))}
                {data.items.length === 0 && <tr><td colSpan={6} className="px-3 py-8 text-center text-ink-3">No entries match.</td></tr>}
              </tbody>
            </table>
          </div>
          <Pager total={data.total} page={data.page} size={data.size} onPage={setPage} />
        </>
      )}
    </Panel>
  );
}
