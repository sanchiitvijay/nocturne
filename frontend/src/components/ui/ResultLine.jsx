/** "123 devices · hint" line above a list. */
export default function ResultLine({ children }) {
  return <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-ink-2">{children}</div>;
}
