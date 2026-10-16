export function Skeleton({ className = "h-5" }) {
  return <div className={`animate-pulse rounded-xl bg-surface-3 ${className}`} aria-hidden />;
}

/** Placeholder list while the first page of a view loads. */
export function SkeletonList({ count = 6, className = "h-40", grid = true }) {
  return (
    <div className={grid ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "flex flex-col gap-2"} aria-busy="true">
      {Array.from({ length: count }, (_, i) => <Skeleton key={i} className={className} />)}
    </div>
  );
}
