/** Thin horizontal bar; `value` is 0–100. */
export default function Meter({ value = 0, color = "var(--brand)", className = "" }) {
  const v = Math.max(0, Math.min(100, value || 0));
  return (
    <span className={`block h-2 w-full overflow-hidden rounded-full bg-surface-3 ${className}`}>
      <span className="block h-full rounded-full transition-[width] duration-700" style={{ width: `${v}%`, background: color }} />
    </span>
  );
}
