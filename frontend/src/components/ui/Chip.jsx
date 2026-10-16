import { compact } from "../../lib/format";

/** Toggle chip used for filters; shows an optional colour swatch and count. */
export function Chip({ on = false, onClick, swatch, count, icon: Icon, children, title, trailing: Trailing }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={on}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold transition-colors ${
        on ? "border-brand-200 bg-brand-50 text-brand" : "border-line bg-surface text-ink-2 hover:border-line-strong hover:text-ink"
      }`}
    >
      {swatch && <span className="size-2.5 rounded-full" style={{ background: swatch }} />}
      {Icon && <Icon className="size-4" aria-hidden />}
      {children}
      {count !== undefined && <span className={`text-xs font-medium ${on ? "text-brand" : "text-ink-3"}`}>{compact(count)}</span>}
      {Trailing && <Trailing className="size-3.5" aria-hidden />}
    </button>
  );
}

/** A labelled row of chips. */
export function ChipRow({ label, children }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {label && <span className="mr-1 w-[72px] flex-none text-xs font-semibold uppercase tracking-wide text-ink-3">{label}</span>}
      {children}
    </div>
  );
}
