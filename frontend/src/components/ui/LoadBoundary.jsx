import NotFoundPage from "../../pages/errors/NotFoundPage";
import ErrorState from "./ErrorState";
import { Skeleton } from "./Skeleton";

/**
 * Standard loading / error handling for a page that fetches one resource:
 * skeleton until the first data, "not found" for 404, retry for other errors.
 */
export default function LoadBoundary({ state, notFound, skeleton, children }) {
  const { data, error, loading, reload } = state;
  if (error && !data) {
    if (error.status === 404) return <NotFoundPage title={notFound?.title} text={error.message} />;
    return <ErrorState error={error} onRetry={() => reload()} />;
  }
  if (!data) return skeleton || (loading ? <Skeleton className="h-56" /> : null);
  return children(data);
}
