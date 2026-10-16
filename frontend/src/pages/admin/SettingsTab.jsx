import { adminApi } from "../../api/endpoints";
import ErrorState from "../../components/ui/ErrorState";
import Panel from "../../components/ui/Panel";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatGrid, StatTile } from "../../components/ui/StatTile";
import { useAsync } from "../../hooks/useAsync";
import { humanize } from "../../lib/format";

const OPEN_BY_DEFAULT = ["app", "diagnostics", "ai", "_secrets"];

export default function SettingsTab() {
  const { data, error, reload } = useAsync(() => adminApi.settings(), []);
  return (
    <Panel title="Effective settings"
      description={data ? <>Read from <span className="font-mono">{data.config_path}</span>. Secrets come from environment variables and are never shown.</> : null}>
      {error && !data ? <ErrorState error={error} onRetry={() => reload()} /> : !data ? <Skeleton className="h-80" /> : (
        <>
          <StatGrid cols="sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
            {Object.entries(data.system).map(([k, v]) => <StatTile key={k} value={<span className="text-base">{String(v)}</span>} label={humanize(k)} />)}
          </StatGrid>
          <div className="mt-4 flex flex-col gap-2">
            {Object.entries(data.config).map(([k, v]) => (
              <details key={k} open={OPEN_BY_DEFAULT.includes(k)} className="rounded-xl border border-line px-4 py-2.5">
                <summary className="cursor-pointer font-semibold">{k === "_secrets" ? "secrets" : k}</summary>
                <pre className="mt-2.5 max-h-96 overflow-auto rounded-lg bg-surface-2 p-3 font-mono text-xs">{JSON.stringify(v, null, 2)}</pre>
              </details>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
