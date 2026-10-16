const control = "rounded-[10px] border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-3 transition-colors focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/25 disabled:opacity-60";

// Full width unless the caller sets a width of its own.
const width = (className) => (/(^|\s)w-/.test(className) ? "" : "w-full");

export function Input({ className = "", ...rest }) {
  return <input className={`${control} ${width(className)} h-10 ${className}`} {...rest} />;
}

export function Select({ className = "", children, ...rest }) {
  return <select className={`${control} ${width(className)} h-10 pr-8 ${className}`} {...rest}>{children}</select>;
}

export function Textarea({ className = "", ...rest }) {
  return <textarea className={`${control} ${width(className)} min-h-24 py-2 ${className}`} {...rest} />;
}

/** Label + control + hint/error. */
export function Field({ label, htmlFor, hint, error, children, className = "" }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      {label && <label htmlFor={htmlFor} className="text-[13px] font-semibold text-ink-2">{label}</label>}
      {children}
      {error ? <small className="text-xs text-p1-ink">{error}</small> : hint ? <small className="text-xs text-ink-3">{hint}</small> : null}
    </div>
  );
}

export function FormError({ message }) {
  if (!message) return null;
  return <div role="alert" className="rounded-[10px] bg-p1-bg px-3 py-2.5 text-[13.5px] text-p1-ink">{message}</div>;
}
