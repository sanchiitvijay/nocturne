import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import Pager from "./Pager";
import { SkeletonList } from "./Skeleton";

/**
 * Paged card list for a `useAsync` state whose data is {items, total, page, size}.
 * Dims while a new page or filter loads; shows skeletons only before the first result.
 */
export default function ListView({ state, renderItem, empty, onPage, skeletonClass = "h-36", gridClass = "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" }) {
  const { data, error, loading, reload } = state;
  if (error && !data) return <ErrorState error={error} onRetry={() => reload()} />;
  if (!data) return <SkeletonList className={skeletonClass} />;
  return (
    <>
      {data.items.length === 0 ? <EmptyState {...empty} />
        : <div className={`${gridClass} transition-opacity ${loading ? "opacity-60" : ""}`}>{data.items.map(renderItem)}</div>}
      <Pager total={data.total} page={data.page} size={data.size} onPage={onPage} />
    </>
  );
}
