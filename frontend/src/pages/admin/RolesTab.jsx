import { LuCheck } from "react-icons/lu";
import ErrorState from "../../components/ui/ErrorState";
import Panel from "../../components/ui/Panel";
import { Skeleton } from "../../components/ui/Skeleton";
import { humanize } from "../../lib/format";

export default function RolesTab({ state }) {
  const { data, error, reload } = state;
  return (
    <Panel title="Roles and what they can do" description="Defined in the [roles] and [permissions] sections of nocturne.toml.">
      {error && !data ? <ErrorState error={error} onRetry={() => reload()} /> : !data ? <Skeleton className="h-64" /> : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wide text-ink-3">
              <tr><th className="px-3 py-2.5">Capability</th>{Object.values(data.roles).map((r) => <th key={r} className="px-3 py-2.5 text-center">{r}</th>)}</tr>
            </thead>
            <tbody>
              {Object.entries(data.permissions).map(([cap, roles]) => (
                <tr key={cap} className="border-t border-line">
                  <td className="px-3 py-2 capitalize">{humanize(cap)}</td>
                  {Object.keys(data.roles).map((k) => (
                    <td key={k} className="px-3 py-2 text-center">
                      {roles.includes(k) ? <LuCheck className="inline size-4 text-good" aria-label="Allowed" /> : <span className="text-ink-3" aria-label="Not allowed">—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
