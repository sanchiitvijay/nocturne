import { useEffect, useState } from "react";
import { LuPlay, LuSquare } from "react-icons/lu";
import { opsApi } from "../../api/endpoints";
import Button from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Field";
import Meter from "../../components/ui/Meter";
import Panel from "../../components/ui/Panel";
import { useLiveEvent } from "../../context/LiveContext";
import { useToast } from "../../context/ToastContext";
import { useAction } from "../../hooks/useAction";

// Bounds of SimRun.interval_ms in app/api/ops.py.
const MIN_GAP_MS = 50, MAX_GAP_MS = 60000;

function statusText(s) {
  if (s.running) return `Running ${s.scenario}: ${s.sent} of ${s.total} sent`;
  if (s.total) return `Finished ${s.scenario}: ${s.sent} of ${s.total} sent`;
  return "Idle";
}

export default function ScenarioRunner({ options }) {
  const toast = useToast();
  const { scenarios, limits } = options;
  const [scenario, setScenario] = useState(scenarios[0]?.id || "");
  const [form, setForm] = useState({ count: String(limits.count), interval: String(limits.interval_ms), site: "" });
  const [status, setStatus] = useState(options.status);
  useEffect(() => { setStatus(options.status); }, [options.status]);
  useLiveEvent("sim", setStatus);

  const [run, running] = useAction(async () => {
    const count = Number(form.count), interval = Number(form.interval);
    if (!Number.isInteger(count) || count < 1 || count > limits.max_count) throw new Error(`Alerts must be a whole number from 1 to ${limits.max_count}.`);
    if (!Number.isFinite(interval) || interval < MIN_GAP_MS || interval > MAX_GAP_MS) throw new Error(`The gap between alerts must be from ${MIN_GAP_MS} to ${MAX_GAP_MS} ms.`);
    const s = await opsApi.simRun({ scenario, count, interval_ms: interval, site: form.site.trim() || null });
    setStatus(s);
    toast(`Simulation started: ${s.total} alerts.`, "ok");
  });
  const [stop, stopping] = useAction(async () => setStatus(await opsApi.simStop()));
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <Panel title="Run a scenario"
      description="Simulated alerts use real devices and flow through the live stream, search, dashboards and triage exactly like imported ones. They carry a striped “Simulated” tag and can be purged in Data Studio.">
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {scenarios.map((s) => (
          <button key={s.id} type="button" onClick={() => setScenario(s.id)} aria-pressed={scenario === s.id}
            className={`flex flex-col gap-1 rounded-xl border p-3.5 text-left transition-colors ${scenario === s.id ? "border-brand bg-brand-50" : "border-line hover:bg-hover"}`}>
            <b className={`text-sm ${scenario === s.id ? "text-brand" : ""}`}>{s.label}</b>
            <span className="text-[12.5px] text-ink-3">{s.text}</span>
          </button>
        ))}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Field label="Alerts (random scenario)" htmlFor="sim-count" hint={`Up to ${limits.max_count}.`}>
          <Input id="sim-count" type="number" min={1} max={limits.max_count} value={form.count} onChange={set("count")} />
        </Field>
        <Field label="Gap between alerts (ms)" htmlFor="sim-gap"><Input id="sim-gap" type="number" min={MIN_GAP_MS} max={MAX_GAP_MS} step={50} value={form.interval} onChange={set("interval")} /></Field>
        <Field label="Limit to site code" htmlFor="sim-site"><Input id="sim-site" value={form.site} onChange={set("site")} placeholder="Any site" /></Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="primary" icon={LuPlay} busy={running} disabled={status.running || !scenario} onClick={run}>Start simulation</Button>
        <Button icon={LuSquare} busy={stopping} disabled={!status.running} onClick={stop}>Stop</Button>
        <div className="min-w-[160px] flex-1">
          <Meter value={status.total ? (100 * status.sent) / status.total : 0} />
          <small className="text-xs text-ink-3">{statusText(status)}</small>
        </div>
      </div>
    </Panel>
  );
}
