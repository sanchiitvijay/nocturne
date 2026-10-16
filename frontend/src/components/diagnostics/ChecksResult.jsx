import { LuActivity, LuGlobe, LuRoute, LuTerminal } from "react-icons/lu";
import { time } from "../../lib/format";
import Fact from "../ui/Fact";

function Check({ ok, icon: Icon, title, detail, children }) {
  return (
    <div className={`flex gap-3 rounded-xl border p-3 ${ok ? "border-good/30 bg-good-bg/40" : "border-p1/30 bg-p1-bg/40"}`}>
      <span className={`grid size-8 flex-none place-items-center rounded-lg ${ok ? "bg-good-bg text-good-ink" : "bg-p1-bg text-p1-ink"}`}><Icon className="size-4" aria-hidden /></span>
      <div className="min-w-0 flex-1 text-[13.5px]">
        <b>{title}</b> {detail && <span className="text-ink-3">{detail}</span>}
        {children}
      </div>
    </div>
  );
}

/** Ping, traceroute, DNS and TCP results from /api/diagnostics or /api/alerts/{id}/checks. */
export default function ChecksResult({ checks: c }) {
  const p = c.ping;
  const samples = p.samples || [];
  const maxRtt = Math.max(...samples.filter((x) => x != null), 1);
  return (
    <div className="flex flex-col gap-2.5">
      <Check ok={p.reachable} icon={LuActivity} title={`Ping ${p.reachable ? "replies" : "no reply"}`}
        detail={`${p.received}/${p.sent} received, ${p.loss_pct}% loss${p.avg_ms ? `, avg ${p.avg_ms} ms (min ${p.min_ms}, max ${p.max_ms})` : ""}`}>
        <div className="mt-2 flex h-7 items-end gap-1">
          {samples.map((s, i) => (s == null
            ? <i key={i} title="timeout" className="h-1 w-3 rounded-sm bg-p1" />
            : <i key={i} title={`${s} ms`} className="w-3 rounded-sm bg-good" style={{ height: Math.max(4, (26 * s) / maxRtt) }} />))}
        </div>
      </Check>
      <Check ok={c.traceroute.completed} icon={LuRoute} title={`Traceroute ${c.traceroute.completed ? "reached the device" : "did not complete"}`} detail={c.traceroute.note}>
        <div className="mt-1.5 flex flex-wrap items-center gap-1 font-mono text-xs">
          {c.traceroute.hops.map((h, i) => (
            <span key={h.hop} className="flex items-center gap-1">
              {i > 0 && <b className="text-ink-3">›</b>}
              <span className={`rounded px-1.5 py-0.5 ${h.host === "*" ? "bg-p1-bg text-p1-ink" : "bg-surface-3"}`} title={h.ms != null ? `${h.ms} ms` : "no reply"}>{h.hop}. {h.host}</span>
            </span>
          ))}
        </div>
      </Check>
      <Check ok={c.dns.ok} icon={LuGlobe} title={`DNS ${c.dns.ok ? "resolves" : "lookup failed"}`}
        detail={<span className="font-mono">{[...(c.dns.forward || []), c.dns.reverse].filter(Boolean).join("  ↔  ") || c.dns.error || ""}</span>} />
      <Check ok={c.tcp.some((t) => t.open)} icon={LuTerminal} title="Service ports">
        <div className="mt-1 flex flex-wrap gap-3">
          {c.tcp.map((t) => <Fact key={t.port} tone={t.open ? "good" : "hot"}>TCP {t.port} {t.open ? `open${t.ms ? ` ${t.ms} ms` : ""}` : "closed"}</Fact>)}
        </div>
      </Check>
      <p className="text-xs text-ink-3">Checked <span className="font-mono">{c.host}</span> at {time(c.ran_at)} in {c.duration_ms} ms{c.cached ? " (cached)" : ""}.</p>
    </div>
  );
}
