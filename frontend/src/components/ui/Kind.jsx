import { KIND_TONE } from "../../lib/domain";

/** Ticket type tag (INC, RITM, TASK, CHG…). */
export default function Kind({ kind }) {
  return <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-bold tracking-wide ${KIND_TONE[kind] || "bg-surface-3 text-ink-2"}`}>{kind || "?"}</span>;
}
