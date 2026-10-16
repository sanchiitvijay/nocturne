import { useEffect, useState } from "react";
import { subscribeInflight } from "../../api/client";

/** Thin bar at the top of the window while foreground API requests are in flight. */
export default function ProgressBar() {
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let t;
    const off = subscribeInflight((n) => {
      clearTimeout(t);
      if (n > 0) t = setTimeout(() => setBusy(true), 120);
      else setBusy(false);
    });
    return () => { off(); clearTimeout(t); };
  }, []);
  return (
    <div className={`pointer-events-none fixed inset-x-0 top-0 z-[90] h-0.5 overflow-hidden transition-opacity ${busy ? "opacity-100" : "opacity-0"}`} aria-hidden>
      <div className="h-full w-1/3 animate-indeterminate bg-brand" />
    </div>
  );
}
