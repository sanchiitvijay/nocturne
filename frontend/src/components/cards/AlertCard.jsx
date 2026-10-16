import { Link } from "react-router-dom";
import { LuActivity, LuArrowDown, LuArrowUp, LuMapPin, LuMinus, LuRefreshCw, LuTicket } from "react-icons/lu";
import { useLabels } from "../../context/AuthContext";
import { categoryIcon } from "../../lib/icons";
import { STATE_TONE, categoryColor, sevColor } from "../../lib/domain";
import { cap, compact, date, time } from "../../lib/format";
import Fact from "../ui/Fact";
import Pill from "../ui/Pill";

const TRANSITION = {
  down: { icon: LuArrowDown, label: "Down", cls: "text-p1-ink" },
  up: { icon: LuArrowUp, label: "Recovered", cls: "text-good-ink" },
};

/** Device names break at separators rather than mid-word. */
export function DeviceName({ name }) {
  const parts = String(name || "").split(/([_\-./])/);
  return <>{parts.map((p, i) => (/^[_\-./]$/.test(p) ? <span key={i}>{p}<wbr /></span> : <span key={i}>{p}</span>))}</>;
}

function SourcePill({ source }) {
  const labels = useLabels();
  if (source === "simulation") return <Pill tone="striped">{labels.source(source)}</Pill>;
  if (source === "custom") return <Pill tone="dashed">{labels.source(source)}</Pill>;
  return null;
}

/**
 * Alert summary card. `compact` renders a one-line row; `selectable` adds a checkbox (bulk actions);
 * `fresh` flashes the card when it just arrived on the live stream.
 */
export default function AlertCard({ alert: e, compact: isCompact = false, selectable = false, selected = false, onSelect, fresh = false }) {
  const labels = useLabels();
  const CatIcon = categoryIcon(e.category);
  const tr = TRANSITION[e.transition] || { icon: LuMinus, label: "Event", cls: "text-ink-3" };
  const TrIcon = tr.icon;
  const resolved = e.state === "resolved";
  const checkbox = selectable && (
    <label className="absolute right-2.5 top-2.5 z-10 grid size-7 cursor-pointer place-items-center rounded-md bg-surface/90 hover:bg-hover" onClick={(ev) => ev.stopPropagation()}>
      <input type="checkbox" checked={selected} onChange={(ev) => onSelect?.(e.id, ev.target.checked)} aria-label={`Select alert ${e.id}`} />
    </label>
  );

  if (isCompact) {
    // A container query lets the same row work in a narrow side panel and a full-width list.
    return (
      <div className={`@container relative ${fresh ? "animate-fresh" : ""}`}>
        <Link to={`/alerts/${e.id}`} className={`flex items-center gap-3 overflow-hidden rounded-xl border border-line bg-surface py-2 pr-3 text-ink hover:border-line-strong hover:no-underline ${selectable ? "pr-12" : ""} ${resolved ? "opacity-65" : ""}`}>
          <span className="w-1 self-stretch" style={{ background: sevColor(e.severity) }} />
          <b className="w-6 flex-none text-xs" style={{ color: sevColor(e.severity) }}>{e.severity}</b>
          <TrIcon className={`size-4 flex-none ${tr.cls}`} aria-label={tr.label} />
          <span className="flex min-w-0 flex-1 flex-col @2xl:flex-row @2xl:items-center @2xl:gap-3">
            <span className="truncate text-[13.5px] font-semibold @2xl:flex-1">{e.name}</span>
            <span className="truncate font-mono text-xs text-ink-2 @2xl:flex-1">{e.device_name || "No device"}</span>
          </span>
          <span className={`hidden flex-none rounded-full px-2 py-0.5 text-[11px] font-semibold @lg:inline ${STATE_TONE[e.state] || ""}`}>{labels.state(e.state)}</span>
          <span className="flex-none text-right text-[11.5px] leading-tight tabular-nums text-ink-3">{time(e.ts)}<br />{date(e.ts)}</span>
        </Link>
        {checkbox}
      </div>
    );
  }

  return (
    <div className={`relative ${fresh ? "animate-fresh rounded-2xl" : ""}`}>
      <Link to={`/alerts/${e.id}`}
        className={`group flex h-full overflow-hidden rounded-2xl border border-line bg-surface text-ink transition-shadow hover:border-line-strong hover:no-underline hover:shadow-card ${resolved ? "opacity-70" : ""}`}>
        <div className="flex w-11 flex-none flex-col items-center gap-1 py-3 text-white" style={{ background: sevColor(e.severity) }}>
          <b className="text-[13px]">{e.severity}</b>
          <TrIcon className="size-4" aria-hidden />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2 p-3.5">
          <div className="flex items-start gap-2.5 pr-7">
            <span className="grid size-8 flex-none place-items-center rounded-lg" title={cap(e.category)}
              style={{ background: `color-mix(in srgb, ${categoryColor(e.category)} 14%, transparent)`, color: categoryColor(e.category) }}>
              <CatIcon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[14.5px] leading-snug">{e.name}</h3>
              <div className="font-mono text-xs text-ink-2"><DeviceName name={e.device_name || "No device"} /></div>
            </div>
            <span className={`flex flex-none items-center gap-1 text-xs font-semibold ${tr.cls}`}><TrIcon className="size-3.5" aria-hidden />{tr.label}</span>
          </div>
          {e.message && <p className="line-clamp-2 text-[13px] text-ink-2">{e.message}</p>}
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {e.ip && <Fact mono>{e.ip}</Fact>}
            {e.site_code && <Fact icon={LuMapPin}>{e.site_code}{e.site_label ? ` ${e.site_label}` : ""}</Fact>}
            {e.tickets > 0 && <Fact icon={LuTicket} tone="link">{e.tickets} ticket{e.tickets > 1 ? "s" : ""}</Fact>}
            {e.repeats > 5 && <Fact icon={LuRefreshCw} tone="hot" title="Same event type on this device">{compact(e.repeats)}× seen</Fact>}
            {e.status_label && <Fact icon={LuActivity} title="Node status reported with the event">Node {e.status_label.toLowerCase()}</Fact>}
          </div>
          <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
            <span className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${STATE_TONE[e.state] || ""}`}>{labels.state(e.state)}</span>
            <SourcePill source={e.source} />
            <span className="text-xs text-ink-3">{cap(e.category)}</span>
            <span className="ml-auto text-right text-[11.5px] leading-tight tabular-nums text-ink-3"><b className="text-ink-2">{time(e.ts)}</b><br />{date(e.ts)}</span>
          </div>
        </div>
      </Link>
      {checkbox}
    </div>
  );
}
