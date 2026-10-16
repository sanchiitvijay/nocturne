import { Link } from "react-router-dom";
import { LuBell, LuClock, LuCpu, LuMapPin, LuTriangleAlert, LuWorkflow } from "react-icons/lu";
import { compact, dur, num } from "../../lib/format";

function Delta({ now, prev, upIsBad = true }) {
  if (prev === null || prev === undefined) return null;
  let text, tone = "";
  if (!prev && !now) text = "No change vs previous period";
  else if (!prev) { text = "New this period"; tone = upIsBad ? "bad" : "good"; }
  else {
    const d = Math.round(((now - prev) / prev) * 100);
    if (!d) text = "Same as previous period";
    else { text = `${d > 0 ? "▲" : "▼"} ${Math.abs(d)}% vs previous period`; tone = (upIsBad ? d > 0 : d < 0) ? "bad" : "good"; }
  }
  return <div className={`mt-1 text-xs ${tone === "bad" ? "text-[#ffb3bc]" : tone === "good" ? "text-[#a8e6bc]" : "text-white/65"}`}>{text}</div>;
}

/** Headline numbers on the navy hero; most link to the matching filtered list. */
export default function KpiStrip({ kpis: k, previous: p = {}, alertsHref }) {
  const tiles = [
    { label: "Open alerts", icon: LuBell, value: num(k.open_alerts), delta: <Delta now={k.open_alerts} prev={p.open_alerts} />, to: alertsHref({ state: "new,acknowledged" }) },
    { label: "Critical (P1)", icon: LuTriangleAlert, value: num(k.p1), delta: <Delta now={k.p1} prev={p.p1} />, to: alertsHref({ severity: "P1" }), alarm: k.p1 > 0 },
    { label: "Devices affected", icon: LuCpu, value: num(k.devices), delta: <Delta now={k.devices} prev={p.devices} />, to: "/devices" },
    { label: "Sites affected", icon: LuMapPin, value: num(k.sites), delta: <Delta now={k.sites} prev={p.sites} />, to: "/sites" },
    { label: "Median time to recover", icon: LuClock, value: dur(k.mttr_minutes),
      delta: <div className="mt-1 text-xs text-white/65">{num(k.outages)} outages closed, {num(k.still_down)} still down</div> },
    { label: "Actionable share", icon: LuWorkflow, value: k.signal_pct == null ? "—" : `${Number(k.signal_pct).toFixed(1)}%`,
      delta: <div className="mt-1 text-xs text-white/65">{compact(k.actionable)} of {compact(k.events)} events need action</div> },
  ];
  return (
    <div className="mt-6 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
      {tiles.map((t, i) => {
        const Icon = t.icon;
        const body = (
          <>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-white/75"><Icon className="size-4" aria-hidden />{t.label}</div>
            <div className={`mt-1.5 text-[28px] font-bold leading-none tabular-nums ${t.alarm ? "text-[#ff9aa6]" : ""}`}>{t.value}</div>
            {t.delta}
          </>
        );
        const cls = `block animate-rise rounded-xl border p-3.5 text-white hover:no-underline ${t.alarm ? "border-[#ff9aa6]/50 bg-[#c8102e]/20" : "border-white/15 bg-white/[0.07]"}`;
        return t.to
          ? <Link key={t.label} to={t.to} className={`${cls} transition-colors hover:bg-white/[0.13]`} style={{ animationDelay: `${0.1 + i * 0.05}s` }}>{body}</Link>
          : <div key={t.label} className={cls} style={{ animationDelay: `${0.1 + i * 0.05}s` }}>{body}</div>;
      })}
    </div>
  );
}
