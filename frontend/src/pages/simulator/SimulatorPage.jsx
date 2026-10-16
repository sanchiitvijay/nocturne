import { opsApi } from "../../api/endpoints";
import ErrorState from "../../components/ui/ErrorState";
import { Skeleton } from "../../components/ui/Skeleton";
import { usePage } from "../../context/PageContext";
import { useAsync } from "../../hooks/useAsync";
import CustomAlertForm from "./CustomAlertForm";
import LiveFeed from "./LiveFeed";
import ScenarioRunner from "./ScenarioRunner";

export default function SimulatorPage() {
  usePage("Alert simulator");
  const { data, error, reload } = useAsync(() => opsApi.simOptions(), []);
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
        {error && !data ? <ErrorState error={error} onRetry={() => reload()} />
          : !data ? <><Skeleton className="h-72" /><Skeleton className="h-96" /></>
            : <><ScenarioRunner options={data} /><CustomAlertForm options={data} /></>}
      </div>
      <LiveFeed />
    </div>
  );
}
