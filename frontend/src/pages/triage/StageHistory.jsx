import { useState } from "react";
import { Link } from "react-router-dom";
import { LuThumbsUp, LuTicket } from "react-icons/lu";
import { alertsApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import Kind from "../../components/ui/Kind";
import Meter from "../../components/ui/Meter";
import Pill from "../../components/ui/Pill";
import Signal from "../../components/ui/Signal";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";
import { scoreColor } from "../../lib/domain";
import { date, dur, stamp } from "../../lib/format";

// Why a ticket matched: link kinds (ci, device, ip, site), weaker "nearby" links, alert-time confirmation, wording, timing, feedback.
const REASON_TONE = {
  ci: "bg-brand-50 text-brand", device: "bg-brand-50 text-brand", ip: "bg-brand-50 text-brand", site: "bg-p4-bg text-p4-ink",
  nearby: "bg-surface-3 text-ink-2", confirmed: "bg-good-bg text-good-ink", text: "bg-surface-3 text-ink-2",
  time: "bg-warn-bg text-warn-ink", feedback: "bg-good-bg text-good-ink",
};

export default function StageHistory({ eventId, history }) {
  const { can } = useAuth();
  const toast = useToast();
  const [helped, setHelped] = useState(() => new Set());
  const [markHelped] = useAction(async (number) => {
    await alertsApi.feedback(eventId, "helpful", number);
    setHelped((s) => new Set(s).add(number));
    toast(`Noted: ${number} helped. Future matches for this device and event type rank it higher.`, "ok");
  });
  const items = history.tickets, tm = history.timing || {};

  return (
    <div className="flex flex-col gap-3">
      {tm.tickets_first && !tm.compared && (
        <Signal>Ticket timing is not compared for this alert: the ticket history covers {date(tm.tickets_first)} – {date(tm.tickets_last)}. Matches rest on device, IP, site and wording.</Signal>
      )}
      {items.length === 0 ? (
        <EmptyState icon={LuTicket} title="No similar tickets found"
          text="Nothing in the ticket history mentions this device, its IP or site, or shares its wording. Import more ticket history in Data Studio." />
      ) : items.map((t) => (
        <div key={t.number} className="flex flex-col gap-2 rounded-xl border border-line p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <Kind kind={t.kind} />
            <Link to={`/tickets/${encodeURIComponent(t.number)}`} className="font-mono font-bold">{t.number}</Link>
            <Pill tone={t.is_open ? "bad" : "good"}>{t.state || ""}</Pill>
            <span className="ml-auto flex w-36 items-center gap-2 text-xs font-semibold tabular-nums">
              <Meter value={t.score} color={scoreColor(t.score)} />{t.score}%
            </span>
          </div>
          <div className="text-[13.5px]">{t.short_description || ""}</div>
          {(t.fixes.length ? t.fixes : t.resolution ? [t.resolution] : []).map((f, i) => (
            <div key={i} className="rounded-lg bg-good-bg px-3 py-2 text-[13px] text-good-ink">{f}</div>
          ))}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1">
              {t.reasons.map((r, i) => <span key={i} className={`rounded-md px-2 py-0.5 text-[11.5px] font-medium ${REASON_TONE[r.kind] || REASON_TONE.text}`}>{r.text}</span>)}
            </div>
            <span className="flex items-center gap-2 text-xs text-ink-3">
              {stamp(t.created_at)}{t.resolve_minutes != null ? `, closed in ${dur(t.resolve_minutes)}` : ""}
              {can("give_feedback") && (
                <Button size="iconSm" variant="subtle" icon={LuThumbsUp} disabled={helped.has(t.number)} onClick={() => markHelped(t.number)}
                  title="This ticket helped" aria-label={`${t.number} helped`} />
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
