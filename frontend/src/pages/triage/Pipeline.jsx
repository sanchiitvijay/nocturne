import { LuCheck, LuX } from "react-icons/lu";
import Spinner from "../../components/ui/Spinner";

export const STAGES = ["Alert analysis", "Log investigation", "Ticket history", "Preliminary checks", "Recommendation"];

/** Progress rail across the five stages. stages: {1: {status, sub}, …}; status: run | done | fail. */
export default function Pipeline({ stages }) {
  return (
    <ol className="grid grid-cols-5 gap-1 border-t border-line pt-4">
      {STAGES.map((name, i) => {
        const n = i + 1, s = stages[n] || {};
        const tone = s.status === "done" ? "bg-good text-white" : s.status === "fail" ? "bg-p1 text-white" : s.status === "run" ? "bg-brand text-on-brand" : "bg-surface-3 text-ink-3";
        return (
          <li key={n}>
            <button type="button" onClick={() => document.getElementById(`stage-${n}`)?.scrollIntoView({ behavior: "smooth" })}
              className="flex w-full flex-col items-center gap-1.5 rounded-xl px-1 py-1.5 text-center hover:bg-hover">
              <span className={`grid size-8 place-items-center rounded-full text-sm font-bold ${tone}`}>
                {s.status === "done" ? <LuCheck className="size-4" /> : s.status === "fail" ? <LuX className="size-4" /> : s.status === "run" ? <Spinner className="size-4" /> : n}
              </span>
              <span className="hidden text-xs font-semibold sm:block">{name}</span>
              <span className="line-clamp-2 min-h-8 text-[11px] text-ink-3">{s.sub || ""}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
