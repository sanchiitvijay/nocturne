import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { LuRefreshCw, LuTriangleAlert } from "react-icons/lu";
import { alertsApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import Pill from "../../components/ui/Pill";
import ErrorState from "../../components/ui/ErrorState";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../context/AuthContext";
import { useLiveEvent } from "../../context/LiveContext";
import { usePage } from "../../context/PageContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";
import { roleLabel } from "../../lib/domain";
import { dur } from "../../lib/format";
import NotFoundPage from "../errors/NotFoundPage";
import Pipeline from "./Pipeline";
import StageAnalysis from "./StageAnalysis";
import StageChecks from "./StageChecks";
import StageHistory from "./StageHistory";
import StageLogs from "./StageLogs";
import StagePanel from "./StagePanel";
import StageRecommendation, { RecommendationActions } from "./StageRecommendation";
import TriageHero from "./TriageHero";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// Each stage stays visible for a moment so the analyst can follow the sweep.
const pace = async (start, min = 380) => { const d = performance.now() - start; if (d < min) await sleep(min - d); };

function recSummary(r) {
  if (r.source === "ai") return `AI${r.cache?.cached ? " (saved)" : ""}, ${r.confidence_label.toLowerCase()} confidence`;
  if (r.source === "fallback") return "Engine fallback";
  return `${r.confidence_label} confidence`;
}

export default function TriagePage() {
  const { id: rawId } = useParams();
  const id = Number(rawId);
  const toast = useToast();
  const [stages, setStages] = useState({});
  const [detail, setDetail] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [history, setHistory] = useState(null);
  const [checks, setChecks] = useState(null);
  const [checksError, setChecksError] = useState("");
  const [rec, setRec] = useState(null);
  const [fatal, setFatal] = useState(null);
  const [runKey, setRunKey] = useState(0);
  const alive = useRef(0);

  const e = detail?.event;
  usePage(e ? `${e.name} on ${e.device_name || "unknown device"}` : `Alert #${rawId}`, [{ label: "Alerts", to: "/alerts" }]);

  const stage = useCallback((n, status, sub) => setStages((s) => ({ ...s, [n]: { status, sub: sub ?? s[n]?.sub } })), []);

  // Orchestrated sweep through the five stages.
  useEffect(() => {
    const run = ++alive.current;
    const live = () => run === alive.current;
    setStages({}); setDetail(null); setAnalysis(null); setHistory(null); setChecks(null); setChecksError(""); setRec(null); setFatal(null);
    if (!Number.isInteger(id) || id <= 0) { setFatal({ status: 404, message: "That alert does not exist." }); return undefined; }

    (async () => {
      let current = 0;
      try {
        current = 1; stage(1, "run", "Reading alert");
        let t = performance.now();
        const d = await alertsApi.detail(id);
        if (!live()) return;
        setDetail(d); await pace(t);
        stage(1, "done", d.device ? roleLabel(d.device.role) : "System event");

        current = 2; stage(2, "run", "Correlating"); t = performance.now();
        const a = await alertsApi.analysis(id);
        if (!live()) return;
        setAnalysis(a); await pace(t);
        stage(2, "done", a.blast_radius.length ? "Site-wide" : a.flap_cycles >= 3 ? "Flapping" : a.outage?.minutes != null ? `Recovered ${dur(a.outage.minutes)}` : `${a.timeline.length} events ±24 h`);

        current = 3; stage(3, "run", "Matching tickets"); t = performance.now();
        const h = await alertsApi.history(id);
        if (!live()) return;
        setHistory(h); await pace(t);
        stage(3, "done", h.tickets.length ? `${h.tickets.length} matches, best ${h.tickets[0].score}%` : "No matches");

        current = 4; stage(4, "run", "Ping, trace, DNS"); t = performance.now();
        try {
          const c = await alertsApi.checks(id);
          if (!live()) return;
          setChecks(c); stage(4, "done", c.verdict);
        } catch (ex) {
          if (!live()) return;
          setChecksError(ex.message); stage(4, "fail", "Skipped");
        }
        await pace(t);

        current = 5;
        const ai = d.ai || {};
        const auto = ai.enabled && ai.configured && ai.mode === "auto" && (ai.auto_severities || []).includes(d.event.severity);
        stage(5, "run", auto ? "Asking AI (saved answers reused)" : "Building plan"); t = performance.now();
        const r = await alertsApi.recommendation(id);
        if (!live()) return;
        setRec(r); await pace(t, 300);
        stage(5, "done", recSummary(r));
      } catch (ex) {
        if (!live()) return;
        if (current === 1) setFatal(ex);
        stage(current, "fail", "Failed");
        if (current > 1) toast(ex.message, "error");
      }
    })();
    return () => { alive.current += 1; };
  }, [id, runKey, stage, toast]);

  const [setState, stateBusy] = useAction(async (target, note = null) => {
    await alertsApi.setState(id, target, note);
    toast(`Alert marked ${target}.`, "ok");
    const d = await alertsApi.detail(id);
    setDetail(d);
    return true;
  });

  const [rerunChecks, checking] = useAction(async () => {
    stage(4, "run", "Running…");
    try {
      const c = await alertsApi.checks(id);
      setChecks(c); setChecksError(""); stage(4, "done", c.verdict);
    } catch (ex) {
      stage(4, "fail", "Failed");
      throw ex;
    }
  });

  const [askAi, asking] = useAction(async (refresh) => {
    stage(5, "run", refresh ? "Refreshing AI answer" : "Asking AI");
    try {
      const r = await alertsApi.askAi(id, refresh);
      setRec(r);
      stage(5, "done", recSummary(r));
      if (r.source === "fallback") toast(`AI not used: ${r.fallback_reason}`, "error");
    } catch (ex) {
      stage(5, "fail", "Failed");
      throw ex;
    }
  });

  useLiveEvent("alert_state", (s) => {
    if (s.id === id) setDetail((d) => (d ? { ...d, event: { ...d.event, state: s.state, owner: s.owner } } : d));
  });

  if (fatal) {
    if (fatal.status === 404) return <NotFoundPage title="Alert not found" text={fatal.message} />;
    return <ErrorState error={fatal} onRetry={() => setRunKey((k) => k + 1)} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {detail ? (
        <TriageHero event={detail.event} busy={stateBusy} onState={setState}>
          <Pipeline stages={stages} />
        </TriageHero>
      ) : (
        <section className="rounded-2xl border border-line bg-surface p-6">
          <Skeleton className="h-9 w-3/5" /><Skeleton className="mt-3 h-5 w-2/5" />
          <div className="mt-6"><Pipeline stages={stages} /></div>
        </section>
      )}

      <StagePanel no={5} title="Recommended response" done={stages[5]?.status === "done"}
        description="Built from this alert’s evidence, the checks and what fixed similar tickets."
        actions={rec && <RecommendationActions r={rec} onAsk={askAi} asking={asking} />}>
        {rec ? <StageRecommendation eventId={id} r={rec} /> : stages[5]?.status === "fail" ? <p className="text-sm text-ink-3">The plan could not be built.</p> : <Skeleton className="h-32" />}
      </StagePanel>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          <StagePanel no={1} title="Alert analysis" done={!!detail} description="The device, its site and what the monitoring tool reported.">
            {detail ? <StageAnalysis detail={detail} analysis={analysis} /> : <Skeleton className="h-36" />}
          </StagePanel>
          <StagePanel no={3} title="Ticket history" done={!!history} description="Similar past tickets, ranked by device/site links, shared wording and timing.">
            {history ? <StageHistory eventId={id} history={history} /> : <Skeleton className="h-40" />}
          </StagePanel>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <StagePanel no={4} title="Preliminary checks" done={!!checks || !!checksError} description="Reachability, path, DNS and service ports for the device."
            actions={(checks || checksError) && <RerunActions checks={checks} onRerun={rerunChecks} busy={checking} />}>
            {checks || checksError ? <StageChecks checks={checks} error={checksError} /> : <Skeleton className="h-36" />}
          </StagePanel>
          <StagePanel no={2} title="Log investigation" done={!!analysis} description="Recovery, flapping, neighbours and the device timeline.">
            {analysis && detail ? <StageLogs analysis={analysis} event={detail.event} /> : <Skeleton className="h-44" />}
          </StagePanel>
        </div>
      </div>
    </div>
  );
}

function RerunActions({ checks, onRerun, busy }) {
  const { can } = useAuth();
  return (
    <>
      {checks && (checks.simulated
        ? <Pill tone="warn" icon={LuTriangleAlert} title="Diagnostics mode is 'simulated' in nocturne.toml">Simulated results</Pill>
        : <Pill tone="good">Live from server</Pill>)}
      {can("run_diagnostics") && <Button size="sm" icon={LuRefreshCw} busy={busy} onClick={() => onRerun()}>Run again</Button>}
    </>
  );
}
