import { LuTriangleAlert, LuRefreshCw } from "react-icons/lu";
import Button from "./Button";

/** Shown in place of content whose request failed, with a retry. */
export default function ErrorState({ error, onRetry, compact = false }) {
  return (
    <div className={`flex flex-col items-center gap-2 text-center ${compact ? "py-4" : "py-10"}`} role="alert">
      <LuTriangleAlert className="size-7 text-p2" aria-hidden />
      <p className="max-w-md text-sm text-ink-2">{error?.message || "This could not be loaded."}</p>
      {onRetry && <Button size="sm" icon={LuRefreshCw} onClick={() => onRetry()}>Try again</Button>}
    </div>
  );
}
