export function StatTile({ value, label, className = "" }) {
  return (
    <div className={`min-w-0 rounded-xl border border-line bg-surface-2 px-3.5 py-3 ${className}`}>
      <div className="truncate text-xl font-bold tabular-nums">{value}</div>
      <div className="mt-0.5 text-xs text-ink-3">{label}</div>
    </div>
  );
}

export function StatGrid({ children, cols = "sm:grid-cols-2 lg:grid-cols-4" }) {
  return <div className={`grid grid-cols-2 gap-2.5 ${cols}`}>{children}</div>;
}
