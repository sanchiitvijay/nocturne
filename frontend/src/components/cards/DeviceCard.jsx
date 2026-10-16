import { Link } from "react-router-dom";
import { LuBell, LuMapPin, LuTicket } from "react-icons/lu";
import { roleIcon } from "../../lib/icons";
import { roleLabel } from "../../lib/domain";
import { compact } from "../../lib/format";
import Fact from "../ui/Fact";

export default function DeviceCard({ device: d, showSite = true }) {
  const Icon = roleIcon(d.role);
  const state = d.node_state === "down" ? "bg-p1" : d.node_state === "up" ? "bg-good" : "bg-line-strong";
  return (
    <Link to={`/devices/${d.id}`} className="relative flex gap-3 rounded-2xl border border-line bg-surface p-3.5 text-ink transition-shadow hover:border-line-strong hover:no-underline hover:shadow-card">
      <span className="grid size-10 flex-none place-items-center rounded-xl bg-brand-50 text-brand" title={roleLabel(d.role)}><Icon className="size-5" aria-hidden /></span>
      <div className="min-w-0 flex-1 pr-4">
        <h3 className="truncate font-mono text-[13.5px]" title={d.name}>{d.name}</h3>
        <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-2">
          <span className="font-mono">{d.ip || "no IP"}</span><span>{roleLabel(d.role)}</span>
        </div>
        {showSite && (
          <div className="mt-1 text-xs">
            {d.site_code ? <Fact icon={LuMapPin} title={d.site_label || ""}>{d.site_code}{d.site_label ? ` ${d.site_label}` : ""}</Fact>
              : <Fact icon={LuMapPin} className="text-ink-3">No site code</Fact>}
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          <Fact icon={LuBell}>{compact(d.event_count)} events</Fact>
          {d.p1 > 0 && <Fact tone="hot">{compact(d.p1)} critical</Fact>}
          {d.tickets > 0 && <Fact icon={LuTicket} tone="link">{d.tickets}</Fact>}
        </div>
      </div>
      <span className={`absolute right-3.5 top-3.5 size-2.5 rounded-full ${state}`} title={d.node_state ? `Last node state: ${d.node_state}` : "No node state"} />
    </Link>
  );
}
