import { Link } from "react-router-dom";
import { LuBell, LuCpu, LuTicket } from "react-icons/lu";
import { address, compact, pct } from "../../lib/format";
import Fact from "../ui/Fact";
import Pill from "../ui/Pill";

export default function SiteCard({ site: s }) {
  const alerts = s.alerts || 0, p1 = s.p1 || 0;
  return (
    <Link to={`/sites/${encodeURIComponent(s.code)}`} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 text-ink transition-shadow hover:border-line-strong hover:no-underline hover:shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-lg font-bold text-brand">{s.code}</span>
        <Pill icon={LuCpu}>{s.devices} device{s.devices === 1 ? "" : "s"}</Pill>
      </div>
      <div>
        <div className="font-semibold">{s.label || "Unlabelled site"}</div>
        <div className="truncate text-xs text-ink-3">{address(s.address)}</div>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-3" title={`${pct(p1, alerts)}% critical`}>
        {p1 > 0 && <i style={{ flexGrow: p1, background: "var(--p1)" }} />}
        {alerts - p1 > 0 && <i style={{ flexGrow: alerts - p1, background: "var(--brand-200)" }} />}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        <Fact icon={LuBell}>{compact(alerts)} alerts</Fact>
        {p1 > 0 && <Fact tone="hot">{compact(p1)} critical</Fact>}
        {s.tickets > 0 && <Fact icon={LuTicket} tone="link">{s.tickets}</Fact>}
      </div>
    </Link>
  );
}
