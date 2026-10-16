import { healthColor } from "../../lib/domain";

export default function HealthRing({ score, size = 56, label }) {
  const r = 22, c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div className="relative grid flex-none place-items-center" style={{ width: size, height: size }} title={`Health ${v}/100`}>
      <svg viewBox="0 0 56 56" className="absolute inset-0 -rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" strokeWidth="6" style={{ stroke: "var(--surface-3)" }} />
        <circle cx="28" cy="28" r={r} fill="none" strokeWidth="6" strokeLinecap="round" strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)} style={{ stroke: healthColor(v), transition: "stroke-dashoffset .8s" }} />
      </svg>
      <b className={size > 60 ? "text-lg" : "text-sm"}>{label ?? v}</b>
    </div>
  );
}
