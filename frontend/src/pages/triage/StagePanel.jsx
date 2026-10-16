/** Numbered section for one triage stage; dimmed until its stage completes. */
export default function StagePanel({ no, title, description, actions, done, children }) {
  return (
    <section id={`stage-${no}`} className={`min-w-0 scroll-mt-24 rounded-2xl border border-line bg-surface p-4 transition-opacity sm:p-5 ${done ? "" : "opacity-70"}`}>
      <header className="mb-4 flex flex-wrap items-start gap-3">
        <span className="grid size-7 flex-none place-items-center rounded-lg bg-brand text-[13px] font-bold text-on-brand">{no}</span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px]">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      {children}
    </section>
  );
}
