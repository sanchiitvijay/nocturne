import { useState } from "react";
import { Link } from "react-router-dom";
import { LuCheck, LuCopy, LuDatabase, LuLayers, LuRefreshCw, LuSparkles, LuThumbsDown, LuThumbsUp, LuTriangleAlert } from "react-icons/lu";
import { alertsApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import KeyValue from "../../components/ui/KeyValue";
import Meter from "../../components/ui/Meter";
import Signal from "../../components/ui/Signal";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";
import { useStoredState } from "../../hooks/useStoredState";
import { scoreColor } from "../../lib/domain";
import { age, dur } from "../../lib/format";

const TAG = "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold";

/** Where the plan came from: AI (fresh or cached), the built-in engine, or a labelled fallback. */
export function SourceTags({ r }) {
  if (r.source === "ai") {
    const c = r.cache || {};
    return (
      <>
        <span className={`${TAG} bg-brand-50 text-brand`} title={`Written by ${r.provider} from this alert's evidence and the matched tickets`}><LuSparkles className="size-3.5" />AI analysis, {r.provider}</span>
        <span className={`${TAG} bg-surface-3 text-ink-2`}>
          <LuLayers className="size-3.5" />{r.grounded_in?.length ? `Based on ${r.grounded_in.join(", ")}` : "Based on this alert's evidence only"}
        </span>
        {c.cached
          ? <span className={`${TAG} bg-surface-3 text-ink-2`} title={`Same evidence as before, so the saved answer was reused (no AI cost). Reused ${c.hits}×.`}><LuDatabase className="size-3.5" />Saved answer, {age(c.age_seconds || 0)}</span>
          : <span className={`${TAG} bg-good-bg text-good-ink`} title="Generated just now and saved for next time"><LuCheck className="size-3.5" />{c.refreshed ? "Refreshed" : "Fresh"} answer{c.latency_ms ? `, ${(c.latency_ms / 1000).toFixed(1)} s` : ""}</span>}
      </>
    );
  }
  if (r.source === "fallback") return <span className={`${TAG} bg-warn-bg text-warn-ink`} title={r.fallback_reason}><LuTriangleAlert className="size-3.5" />Fallback: built-in engine</span>;
  return <span className={`${TAG} bg-surface-3 text-ink-2`} title="Rules, correlation and ticket history; no AI involved"><LuLayers className="size-3.5" />Built-in engine</span>;
}

function StepTag({ source }) {
  const cls = "flex-none rounded-md px-1.5 py-0.5 text-[11px] font-semibold not-italic";
  if (source === "ai") return <em className={`${cls} bg-brand-50 text-brand`}>AI</em>;
  if (source === "playbook") return <em className={`${cls} bg-surface-3 text-ink-2`}>Playbook</em>;
  if (source === "correlation") return <em className={`${cls} bg-p4-bg text-p4-ink`}>Correlation</em>;
  if (source === "dedupe") return <em className={`${cls} bg-p4-bg text-p4-ink`}>Avoid duplicate</em>;
  return <em className={`${cls} bg-good-bg text-good-ink`} title={`What fixed ${source}`}>Worked in {source}</em>;
}

export function RecommendationActions({ r, onAsk, asking }) {
  const { can } = useAuth();
  const canAI = r.ai?.configured && can("ai_refine");
  return (
    <>
      <SourceTags r={r} />
      {canAI && r.source === "ai" && <Button size="sm" icon={LuRefreshCw} busy={asking} onClick={() => onAsk(true)} title="Ignore the saved answer and ask the AI again">Refresh AI answer</Button>}
      {canAI && r.source !== "ai" && <Button size="sm" icon={LuSparkles} busy={asking} onClick={() => onAsk(false)}>Ask AI</Button>}
    </>
  );
}

export default function StageRecommendation({ eventId, r }) {
  const { can } = useAuth();
  const toast = useToast();
  const [done, setDone] = useStoredState(`nocturne-steps-${eventId}`, []);
  const [voted, setVoted] = useState(false);
  const [vote, voting] = useAction(async (verdict) => {
    await alertsApi.feedback(eventId, verdict);
    setVoted(true);
    toast("Thanks — feedback recorded.", "ok");
  });
  const toggleStep = (i) => setDone((d) => (d.includes(i) ? d.filter((x) => x !== i) : [...d, i]));
  const copyNote = async () => {
    try {
      await navigator.clipboard.writeText(r.work_note);
      toast("Work note copied to the clipboard.", "ok");
    } catch {
      toast("Copy failed — select the text and copy it manually.", "error");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {r.source === "fallback" && (
        <Signal tone="warning">AI was not used: {r.fallback_reason}. This plan comes from the built-in engine (rules, correlation and ticket history).</Signal>
      )}
      <div className="grid gap-5 lg:grid-cols-12">
        <div className="flex flex-col gap-4 lg:col-span-8">
          <p className="rounded-xl border-l-4 border-brand bg-brand-50 p-4 text-[15px] font-medium leading-relaxed">{r.hypothesis}</p>
          {r.engine_view && (
            <details className="text-[13.5px] text-ink-2">
              <summary className="cursor-pointer text-ink-3">Compare with the built-in engine's view</summary>
              <p className="mt-2">{r.engine_view}</p>
            </details>
          )}
          <div className="flex items-center gap-3">
            <b className="min-w-[150px] text-sm">Confidence {r.confidence_label}</b>
            <Meter value={r.confidence} color={scoreColor(r.confidence, { high: 75, mid: 50 })} />
            <span className="text-sm tabular-nums">{r.confidence}%</span>
          </div>
          <div>
            <h4 className="mb-2 text-sm">Next steps <span className="font-normal text-ink-3">(select a step to tick it off)</span></h4>
            <ol className="flex flex-col gap-1.5">
              {r.steps.map((s, i) => {
                const ticked = done.includes(i);
                return (
                  <li key={i}>
                    <button type="button" onClick={() => toggleStep(i)} aria-pressed={ticked}
                      className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left text-[13.5px] transition-colors ${ticked ? "border-good/40 bg-good-bg/50" : "border-line hover:bg-hover"}`}>
                      <span className={`grid size-6 flex-none place-items-center rounded-full text-xs font-bold ${ticked ? "bg-good text-white" : "bg-surface-3 text-ink-2"}`}>
                        {ticked ? <LuCheck className="size-3.5" /> : i + 1}
                      </span>
                      <span className={`min-w-0 flex-1 ${ticked ? "text-ink-3 line-through" : ""}`}>
                        {s.text}{s.why && <><br /><small className="text-ink-3 no-underline">{s.why}</small></>}
                      </span>
                      <StepTag source={s.source} />
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
          {r.watch_outs?.length > 0 && <Signal tone="warning"><b>Watch out:</b> {r.watch_outs.join("; ")}</Signal>}
        </div>
        <div className="flex flex-col gap-4 lg:col-span-4">
          <div>
            <h4 className="mb-2 text-sm">Evidence</h4>
            <div className="flex flex-col gap-1.5">
              {r.signals.length ? r.signals.map((s, i) => <Signal key={i} tone={s.tone}>{s.text}</Signal>)
                : <p className="text-sm text-ink-3">No strong signals; the plan follows the category playbook.</p>}
            </div>
          </div>
          <KeyValue items={[
            ["Route to", r.assignment_group || "No history yet"],
            ["Typical fix time", r.expected_minutes != null ? `${dur(r.expected_minutes)} (similar closed tickets)` : "Not enough closed history"],
            ["Similar tickets", r.based_on.length
              ? <span className="flex flex-wrap gap-x-2">{r.based_on.map((n) => <Link key={n} className="font-mono" to={`/tickets/${encodeURIComponent(n)}`}>{n}</Link>)}</span>
              : "None strong enough"],
          ]} />
          <div><Button variant="primary" size="sm" icon={LuCopy} onClick={copyNote}>Copy work note</Button></div>
          {can("give_feedback") && (
            <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
              {voted ? "Feedback recorded." : <>Was this useful?
                <Button size="sm" variant="subtle" icon={LuThumbsUp} disabled={voting} onClick={() => vote("helpful")}>Yes</Button>
                <Button size="sm" variant="subtle" icon={LuThumbsDown} disabled={voting} onClick={() => vote("not_helpful")}>No</Button></>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
