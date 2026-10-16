import { Link } from "react-router-dom";
import { LuClock, LuLink, LuMapPin } from "react-icons/lu";
import { kindColor } from "../../lib/domain";
import { dur, stamp } from "../../lib/format";
import Fact from "../ui/Fact";
import Kind from "../ui/Kind";
import Pill from "../ui/Pill";

export default function TicketCard({ ticket: t }) {
  const sites = t.sites || [];
  return (
    <Link to={`/tickets/${encodeURIComponent(t.number)}`}
      className="flex flex-col gap-2.5 overflow-hidden rounded-2xl border border-line border-l-4 bg-surface p-3.5 text-ink transition-shadow hover:border-line-strong hover:no-underline hover:shadow-card"
      style={{ borderLeftColor: kindColor(t.kind) }}>
      <div className="flex flex-wrap items-center gap-2">
        <Kind kind={t.kind} />
        <span className="font-mono text-[13px] font-semibold">{t.number}</span>
        <Pill tone={t.is_open ? "bad" : "good"}>{t.state || (t.is_open ? "Open" : "Closed")}</Pill>
        <span className="ml-auto">{t.links ? <Fact icon={LuLink} tone="link">{t.links} link{t.links > 1 ? "s" : ""}</Fact> : <Fact className="text-ink-3">Unlinked</Fact>}</span>
      </div>
      <h3 className="line-clamp-2 text-[14.5px]">{t.short_description || "No description"}</h3>
      {t.resolution && <div className="line-clamp-3 rounded-lg bg-good-bg px-3 py-2 text-[13px] text-good-ink">{t.resolution}</div>}
      <div className="mt-auto flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-3">
        <Fact icon={LuClock}>{t.created_at ? stamp(t.created_at) : "No date"}</Fact>
        {t.resolve_minutes != null && <Fact>Resolved in {dur(t.resolve_minutes)}</Fact>}
        {sites.length > 0 && <Fact icon={LuMapPin}>{sites.slice(0, 4).join(", ")}{sites.length > 4 ? "…" : ""}</Fact>}
      </div>
    </Link>
  );
}
