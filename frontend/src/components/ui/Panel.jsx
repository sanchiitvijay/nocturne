/** A card-like section with an optional header (title, description, actions). */
export default function Panel({ title, description, actions, children, className = "", bodyClassName = "", id, badge }) {
  return (
    <section id={id} className={`min-w-0 rounded-2xl border border-line bg-surface p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5">
              {badge}
              {title && <h2 className="text-[17px]">{title}</h2>}
            </div>
            {description && <p className="mt-1 text-[13px] text-ink-3">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
